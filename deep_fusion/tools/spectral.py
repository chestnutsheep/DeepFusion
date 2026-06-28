"""频谱分析 MCP 工具 — 数据由 CSV 传入，不绑定任何数据源。

提供两个工具:
  cycle_detect  — 8种频谱检测 + 三级加权投票 + 相位推断
  cycle_phase   — CF 带通滤波 + 相位推断

核心算法驻在 shared/spectral.py，本层只做编排和格式化。
"""
from __future__ import annotations

import asyncio
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd
from pydantic import Field

from ..server import mcp
from ..shared.spectral import (
    _fft_psd_period,
    _acf_period,
    _wavelet_period,
    _emd_period,
    _lomb_scargle_period,
    _music_period,
    _esprit_period,
    _mem_period,
    ThreeLevelVoter,
    phase_from_waveform,
    cf_bandpass,
)

_METHOD_MAP = {
    "fft": ("FFT", _fft_psd_period),
    "acf": ("ACF", _acf_period),
    "wavelet": ("小波", _wavelet_period),
    "emd": ("EMD", _emd_period),
    "lomb": ("Lomb-Scargle", _lomb_scargle_period),
    "music": ("MUSIC", _music_period),
    "esprit": ("ESPRIT", _esprit_period),
    "mem": ("MEM", _mem_period),
}

_PHASE_NAMES = {0: "未知", 1: "回升期(复苏)", 2: "繁荣期", 3: "衰退期", 4: "萧条期"}


def _detect(
        series: list[float],
        methods: list[str] | None = None,
        target_band: tuple[float, float] = (3, 100),
) -> dict[str, Any]:
    """核心检测逻辑（纯 Python API，也可被其他模块 import）。"""
    arr = np.asarray(series, dtype=np.float64)
    arr_z = (arr - arr.mean()) / (arr.std() + 1e-12)

    if methods is None:
        methods = ["fft", "acf", "wavelet", "music"]

    individual = {}
    voters = []

    for key in methods:
        if key not in _METHOD_MAP:
            continue
        label, fn = _METHOD_MAP[key]
        try:
            result = fn(arr_z)
            period = result.get("period") or result.get("dominant_period")
            conf = result.get("confidence", 0)
            success = result.get("success", False)

            individual[key] = {
                "label": label,
                "period": round(period, 2) if period else None,
                "confidence": round(conf, 4),
                "success": success,
            }

            if period and conf > 0.3 and success:
                voters.append((period, conf, label))
        except Exception as e:
            individual[key] = {"label": label, "error": str(e)[:60]}

    # 三级加权投票
    voting_result = None
    if len(voters) >= 2:
        try:
            voter = ThreeLevelVoter()
            voting_result = voter.vote(voters)
            if isinstance(voting_result, dict):
                voting_result = voting_result.get("period") or voting_result.get(
                    "dominant_period"
                )
        except Exception:
            total_w = sum(w for _, w, _ in voters)
            if total_w > 0:
                voting_result = sum(p * w for p, w, _ in voters) / total_w

    # CF 带通 + 相位推断
    low_yr, high_yr = target_band
    try:
        bp = cf_bandpass(arr_z, low_yr, high_yr)
        bp_cycle = np.array(bp["cycle"])
        bp_cycle = (bp_cycle - bp_cycle.mean()) / (bp_cycle.std() + 1e-12)

        phase = phase_from_waveform(bp_cycle.tolist(), current_idx=-1)
        current_val = float(bp_cycle[-1])
        prev_val = float(bp_cycle[-2]) if len(bp_cycle) > 1 else 0
        direction = "上升" if current_val > prev_val else "下降"
        cycle_strength = float(bp_cycle.std())
    except Exception:
        phase = {"phase": None, "confidence": 0}
        current_val = 0.0
        direction = "未知"
        cycle_strength = 0.0

    return {
        "individual_results": individual,
        "voters": [(round(p, 2), round(w, 2), n) for p, w, n in voters],
        "voting_period": round(voting_result, 2) if voting_result else None,
        "phase": {
            "number": phase.get("phase"),
            "name": _PHASE_NAMES.get(phase.get("phase"), "未知"),
            "confidence": round(phase.get("confidence", 0), 4),
        },
        "current": {
            "value": round(current_val, 4),
            "direction": direction,
            "cycle_strength": round(cycle_strength, 4),
        },
        "method_count": len(methods),
        "voter_count": len(voters),
    }


def _phase(
        series: list[float],
        low_yr: float = 40,
        high_yr: float = 70,
) -> dict[str, Any]:
    """CF 带通 + 相位推断（纯 Python API）。"""
    arr = np.asarray(series, dtype=np.float64)
    arr_z = (arr - arr.mean()) / (arr.std() + 1e-12)

    bp = cf_bandpass(arr_z, low_yr, high_yr)
    cycle = np.array(bp["cycle"])
    cycle_z = (cycle - cycle.mean()) / (cycle.std() + 1e-12)

    phase = phase_from_waveform(cycle_z.tolist(), current_idx=-1)

    return {
        "phase": {
            "number": phase.get("phase"),
            "name": _PHASE_NAMES.get(phase.get("phase"), "未知"),
            "confidence": round(phase.get("confidence", 0), 4),
        },
        "current_value": round(float(cycle_z[-1]), 4),
        "direction": "上升" if float(cycle_z[-1]) > float(cycle_z[-2]) else "下降",
        "cycle_strength": round(float(cycle_z.std()), 4),
        "zscore": [round(float(x), 4) for x in cycle_z],
    }


# ═══════════════════════════════════════════════════════════
# MCP 工具
# ═══════════════════════════════════════════════════════════


@mcp.tool(
    name="cycle_detect",
    description="频谱周期检测：对输入时间序列运行 FFT/ACF/小波/MUSIC 等频谱分析+三级投票，输出检测到的周期、置信度和当前相位",
)
async def cycle_detect(
        data_csv: str = Field(
            description="CSV，至少两列: period(时间), value(数值)。示例:\nperiod,value\n2000,100\n2001,102"
        ),
        methods: str = Field(
            "fft,acf,wavelet,music",
            description="检测方法，逗号分隔: fft, acf, wavelet, emd, lomb, music, esprit, mem",
        ),
        target_low: float = Field(3, description="目标周期下限"),
        target_high: float = Field(100, description="目标周期上限"),
) -> str:
    try:
        df = pd.read_csv(StringIO(data_csv))
    except Exception as e:
        return f"CSV解析失败: {e}"

    if df.empty:
        return "数据为空"

    val_col = _find_value_col(df)
    values = df[val_col].dropna().tolist()
    if len(values) < 10:
        return f"数据太少 ({len(values)}个)"

    ms = [m.strip() for m in methods.split(",") if m.strip() in _METHOD_MAP]
    if not ms:
        ms = ["fft", "acf", "wavelet", "music"]

    # CPU 密集的频谱分析丢入 executor
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, _detect, values, ms, (target_low, target_high))

    lines = [
        "=== 频谱周期检测报告 ===",
        f"方法: {', '.join(ms)}",
        f"样本数: {len(values)}",
        "",
        "── 各方法检测结果 ──",
    ]
    for key, info in res["individual_results"].items():
        if "error" in info:
            lines.append(f"  {info['label']:15s} ❌ {info['error']}")
        else:
            p = info.get("period")
            c = info.get("confidence", 0)
            ok = "✅" if info.get("success") else "⚠️"
            p_str = f"{p:.1f}" if p else "—"
            lines.append(f"  {info['label']:15s} 周期={p_str:>8}  置信度={c:.2f}  {ok}")

    vp = res.get("voting_period")
    if vp:
        lines.extend([
            "",
            f"三级加权投票 → 主周期: {vp:.1f}",
            *[f"  {n}: {p:.1f}年 (权重={w:.2f})" for p, w, n in res.get("voters", [])],
        ])
    else:
        lines.extend(["", "三级投票: 有效票数不足"])

    ph = res.get("phase", {})
    cur = res.get("current", {})
    lines.extend([
        "",
        "── 当前相位 ──",
        f"  阶段: {ph.get('name', '—')} (#{ph.get('number')})",
        f"  置信度: {ph.get('confidence', 0):.2f}",
        f"  PC1值: {cur.get('value', 0):+.4f}",
        f"  方向: {cur.get('direction', '—')}",
        f"  周期强度: {cur.get('cycle_strength', 0):.4f}",
    ])

    return "\n".join(lines)


@mcp.tool(
    name="cycle_phase",
    description="周期相位判断：对输入时间序列运行 CF 带通滤波 + 相位推断",
)
async def cycle_phase(
        data_csv: str = Field(description="CSV，包含 period,value 两列"),
        low_yr: float = Field(40, description="带通滤波低端（年）"),
        high_yr: float = Field(70, description="带通滤波高端（年）"),
) -> str:
    try:
        df = pd.read_csv(StringIO(data_csv))
    except Exception as e:
        return f"CSV解析失败: {e}"

    if df.empty:
        return "数据为空"

    val_col = _find_value_col(df)
    values = df[val_col].dropna().tolist()
    if len(values) < 20:
        return f"数据太少 ({len(values)}个)"

    # CPU 密集的 CF 带通滤波丢入 executor
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, _phase, values, low_yr, high_yr)
    ph = res["phase"]

    return (
        f"=== 周期相位判断 (CF {low_yr:.0f}-{high_yr:.0f}) ===\n"
        f"阶段: {ph['name']} (#{ph['number']})\n"
        f"置信度: {ph['confidence']:.2f}\n"
        f"PC1当前值: {res['current_value']:+.4f}\n"
        f"方向: {res['direction']}\n"
        f"周期强度: {res['cycle_strength']:.4f}"
    )


def _find_value_col(df: pd.DataFrame) -> str:
    for c in ["value", "val", "close", "price", "指数", "值"]:
        if c in df.columns:
            return c
    return df.columns[-1]
