"""最优资产配置结构（Optimal Asset Allocation）

================================================================================
设计依据（学术界 / 行业共识）
================================================================================
后端已有的「四周期引擎」（基钦/朱格拉/库兹涅茨/康波）输出每个周期的
标准化位置 `composite_z`（连续，≈N(0,1)）与离散相位 `phase_name`。
这些周期位置天然刻画了经济所处的「扩张 / 收缩」regime，正是
战术资产配置（Tactical Asset Allocation, TAA）的经典输入。

综合主流共识，本模块采用「**战略基准（风险平价）+ 周期 regime 战术倾斜**」双层框架：

1. 战略基准（Strategic Baseline）—— 风险平价（Risk Parity / "All Weather"）
   - Bridgewater All Weather、Qian(2005)、Invesco 等 widely-used 实践表明：
     让每类资产对组合的风险贡献（= 权重 × 边际风险）相等，比 60/40 在
     跨 regime 下更稳健。实现上等价于「逆波动率加权」(inverse-vol weighting)，
     即 w_i ∝ 1/σ_i（在资产间低相关假设下，逆波动 ≈ 等风险贡献）。
   - 资产长期年化波动率采用学界/业界长期经验值（A 股 + 全球视角）：
       股票 22% / 债券 5% / 商品 20% / 现金 0.5%

2. 战术倾斜（Tactical Overlay）—— 周期 regime 倾斜
   - de Longis & Ellis (Invesco J.P.Morgan 2023, "Tactical Asset Allocation,
     Risk Premia, and the Business Cycle")、Faber (2007, GTAA)、Kritzman et al.
     的 regime-switching 研究一致指出：用连续（而非二元）的周期/趋势指标驱动
     「risk-on ↔ risk-off」倾斜，能稳定提升夏普。
   - 本模块以四个周期 `composite_z` 的等权均值为 regime 信号
     （z>0 高于趋势=扩张，z<0 低于趋势=收缩），映射为 tilt∈[-1,+1]。
   - risk-on 组合（股票/商品超配、债券/现金低配）与 risk-off 组合
     （反向）各自仍用逆波动加权，仅对「风险资产 vs 安全资产」施加偏置，
     保证两极端组合自身也是风险平价风格。

3. 合成：final = blend(neutral, risk_on/risk_off by tilt, 战略权重 0.7)
   core-satellite / 战略-战术 70/30 混合是机构标准做法（Vanguard、BlackRock 白皮书）。

所有输入来自 `cycle_nesting`（已缓存、每日增量刷新），故每次调用都基于
最新实时周期数据动态计算，天然「每日新鲜」。
================================================================================
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any

from pydantic import Field

from ..cache import CacheKey
from ..server import mcp

logger = logging.getLogger(__name__)

# ── 资产类别（与后端周期引擎、前端统一为 股票/债券/商品/现金）─────────────
ASSET_CLASSES = ["股票", "债券", "商品", "现金"]

# 长期年化波动率经验值（学界/业界共识，跨市场长期估计）
#  股票: ~22% (A股+全球权益长期波动)  债券: ~5%  商品: ~20%
_LONG_RUN_VOL: dict[str, float] = {
    "股票": 0.22,
    "债券": 0.05,
    "商品": 0.20,
}

# 风险资产（risk-on 受益）/ 安全资产（risk-off 受益）分组（仅风险资产参与平价）
_RISK_ON = ["股票", "商品"]
_RISK_OFF = ["债券"]

# 现金作为流动性缓冲层（不参与逆波动平价，否则近零波动会吸走全部权重）
#  基准 8%，regime 倾斜在 [CASH_MIN, CASH_MAX] 内调整
CASH_BASE = 0.08
CASH_MIN = 0.03
CASH_MAX = 0.25

# 战略层占比（战略基准 vs 战术倾斜的融合权重）
STRATEGIC_WEIGHT = 0.70
TACTICAL_WEIGHT = 0.30

# regime 信号 → tilt 的灵敏度（|z|≈1.67 时达到满倾斜）
_TILT_GAIN = 0.6

# 周期权重（康波周期极长、端点噪声大，给予较低权重；其余等权）
_CYCLE_WEIGHTS = {
    "kitchin": 1.0,
    "juglar": 1.0,
    "kuznets": 1.0,
    "kondratiev": 0.5,
}


def _inverse_vol_weights(vol: dict[str, float], bias: dict[str, float] | None = None) -> dict[str, float]:
    """逆波动率加权（风险平价近似），仅对传入资产集合生效。

    Args:
        vol:   资产 → 年化波动率
        bias:  可选，资产 → 偏置系数（>1 降低权重=防御，<1 提高权重=进攻）。
                用于构造 risk-on / risk-off 组合。
    Returns:
        归一化后权重 dict（和为 1）。
    """
    assets = list(vol.keys())
    eff_vol = {}
    for a in assets:
        b = bias.get(a, 1.0) if bias else 1.0
        eff_vol[a] = max(vol[a] * b, 1e-6)
    inv = {a: 1.0 / eff_vol[a] for a in assets}
    total = sum(inv.values())
    return {a: inv[a] / total for a in assets}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _latest_nesting() -> tuple[dict[str, Any], str | None]:
    """取 cycle_nesting 最新一期（最后一条）的逐周期 z / 相位。

    Returns:
        (entry, data_date) — entry 含 {kitchin_z, kitchin_phase, kitchin_name, ...}
        data_date 为该期 period（年份）。
    """
    from ..tools.cycles import cycle_nesting

    raw = cycle_nesting()
    rows = json.loads(raw) if isinstance(raw, str) else raw
    if not rows:
        return {}, None
    return rows[-1], str(rows[-1].get("period", ""))


def _regime_signal(entry: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """由四周期 composite_z 合成 regime 信号。

    Returns:
        (tilt, per_cycle_z) — tilt∈[-1, +1]（+1 全面扩张/risk-on，-1 收缩/risk-off）
    """
    z_sum = 0.0
    w_sum = 0.0
    per_cycle_z: dict[str, float] = {}
    for cid, w in _CYCLE_WEIGHTS.items():
        key = f"{cid}_z"
        z = entry.get(key)
        if z is None:
            continue
        per_cycle_z[cid] = float(z)
        z_sum += z * w
        w_sum += w
    regime_z = (z_sum / w_sum) if w_sum > 0 else 0.0
    # 连续映射：tanh 平滑饱和，避免极端 z 过度倾斜
    tilt = _clip(math.tanh(regime_z * _TILT_GAIN), -1.0, 1.0)
    return tilt, per_cycle_z


def _compute_allocation() -> dict[str, Any]:
    """核心计算：风险平价基准(风险资产) + 现金流动性缓冲 + 周期 regime 战术倾斜。

    设计要点（共识实践）：
    - 风险平价（逆波动加权）只对风险资产(股票/债券/商品)生效，因现金波动≈0
      若纳入会吸走全部权重（87%现金），违背 All Weather 本意。
    - 现金作为流动性缓冲层：基准 CASH_BASE，按 regime 在 [CASH_MIN, CASH_MAX] 倾斜。
    - 风险资产桶内部再做 risk-on/risk-off 倾斜（连续 z 驱动，非二元）。
    """
    entry, data_date = _latest_nesting()

    # 1) 战略基准：风险资产逆波动平价
    w_neutral = _inverse_vol_weights(_LONG_RUN_VOL)

    # 2) 两个战术极端（风险资产桶内，仍逆波动风格，仅对风险/安全资产施加偏置）
    w_risk_on = _inverse_vol_weights(
        _LONG_RUN_VOL, bias={a: 0.6 for a in _RISK_ON} | {a: 1.5 for a in _RISK_OFF}
    )
    w_risk_off = _inverse_vol_weights(
        _LONG_RUN_VOL, bias={a: 1.5 for a in _RISK_ON} | {a: 0.6 for a in _RISK_OFF}
    )

    # 3) regime 信号（四周期 composite_z 连续合成）
    tilt, per_cycle_z = _regime_signal(entry)
    alpha = (tilt + 1.0) / 2.0  # ∈[0,1]，1=全 risk-on
    w_risky_tactical = {
        a: alpha * w_risk_on[a] + (1.0 - alpha) * w_risk_off[a] for a in _LONG_RUN_VOL
    }

    # 4) 风险资产桶：战略-战术融合
    risky_neutral = {a: w_neutral[a] for a in _LONG_RUN_VOL}
    risky_blend = {
        a: STRATEGIC_WEIGHT * risky_neutral[a] + TACTICAL_WEIGHT * w_risky_tactical[a]
        for a in _LONG_RUN_VOL
    }

    # 5) 现金流动性缓冲：regime 倾斜（risk-on→减持现金，risk-off→增持）
    cash = _clip(CASH_BASE - tilt * (CASH_MAX - CASH_MIN) / 2.0, CASH_MIN, CASH_MAX)

    # 6) 风险资产桶缩放至 (1 - cash)
    risky_scale = 1.0 - cash
    final = {a: risky_blend[a] * risky_scale for a in _LONG_RUN_VOL}
    final["现金"] = cash
    # 归一化（防浮点误差）
    s = sum(final.values())
    final = {a: round(final[a] / s, 6) for a in ASSET_CLASSES}

    # 7) 周期输入快照（透明展示）
    cycle_snapshot = []
    for cid in ["kitchin", "juglar", "kuznets", "kondratiev"]:
        cycle_snapshot.append({
            "cycle": cid,
            "z": round(per_cycle_z.get(cid, 0.0), 4) if cid in per_cycle_z else None,
            "phase": entry.get(f"{cid}_phase", 0),
            "phase_name": entry.get(f"{cid}_name", "—"),
        })

    regime_label = "扩张(风险偏好上升)" if tilt > 0.15 else (
        "收缩(防御偏好上升)" if tilt < -0.15 else "中性(均衡)"
    )

    return {
        "weights": {a: final[a] for a in ASSET_CLASSES},
        "weights_pct": {a: round(final[a] * 100, 2) for a in ASSET_CLASSES},
        "regime": {
            "tilt": round(tilt, 4),
            "label": regime_label,
        },
        "methodology": {
            "strategic": "风险平价(Risk Parity / 逆波动率加权, All Weather 风格, 仅风险资产)",
            "cash_sleeve": f"流动性缓冲基准{CASH_BASE*100:.0f}%，regime倾斜区间[{CASH_MIN*100:.0f}%,{CASH_MAX*100:.0f}%]",
            "tactical": "四周期 composite_z regime 倾斜(de Longis&Ellis 2023 / Faber 2007 风格)",
            "blend": f"战略{int(STRATEGIC_WEIGHT*100)}% + 战术{int(TACTICAL_WEIGHT*100)}%",
            "strategic_weights": {a: round(w_neutral[a], 4) for a in _LONG_RUN_VOL},
            "risk_on_weights": {a: round(w_risk_on[a], 4) for a in _LONG_RUN_VOL},
            "risk_off_weights": {a: round(w_risk_off[a], 4) for a in _LONG_RUN_VOL},
            "long_run_vol": _LONG_RUN_VOL,
        },
        "cycles": cycle_snapshot,
        "data_date": data_date,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


@mcp.tool(
    name="asset_allocation",
    description=(
        "最优资产配置结构：基于四周期(基钦/朱格拉/库兹涅茨/康波)实时 regime 信号，"
        "采用「风险平价战略基准 + 周期战术倾斜」共识框架动态计算 股票/债券/商品/现金 配比。"
        "每次调用基于最新周期数据实时计算，结果每日新鲜。"
    ),
)
def asset_allocation() -> str:
    _ck = CacheKey.init("asset_allocation_v1", ttl=86400, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    try:
        result = _compute_allocation()
    except Exception as e:  # 周期数据缺失/异常时降级为纯风险平价 + 现金缓冲
        logger.warning("asset_allocation 计算失败，降级为风险平价+现金缓冲: %s", e)
        w = _inverse_vol_weights(_LONG_RUN_VOL)
        risky_scale = 1.0 - CASH_BASE
        final = {a: round(w[a] * risky_scale, 6) for a in _LONG_RUN_VOL}
        final["现金"] = CASH_BASE
        result = {
            "weights_pct": {a: round(final[a] * 100, 2) for a in ASSET_CLASSES},
            "regime": {"tilt": 0.0, "label": "数据不足(风险平价+现金缓冲)"},
            "methodology": {"strategic": "风险平价(降级)", "tactical": "无", "blend": "100% 战略", "cash_sleeve": f"流动性缓冲{CASH_BASE*100:.0f}%"},
            "cycles": [],
            "data_date": None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "degraded": True,
        }
    text = json.dumps(result, ensure_ascii=False)
    _ck.set(text)
    return text
