"""Kondratiev wave analysis"""
import logging

import numpy as np

from ....shared.chart_helpers import (
    setup_chart_font, apply_phase_shading, setup_date_axes, setup_matplotlib_agg,
)
from ....shared.phase_utils import KOND_RENAME
from .engine import _zscore as _simple_zscore  # 复用 engine 的 Z-score，消除重复

setup_matplotlib_agg()
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
def _compute_kondratiev(method: str = "pca"):
    method = method.lower()
    if method == "wavelet":
        return _calc_kondratiev_wavelet()
    elif method == "bandpass":
        return _calc_kondratiev_bandpass()
    from ....shared.utils import compute_kondratiev as _ck

    result = _ck()
    if not result.get("pca1"):
        return result, []
    return result, result["pca1"]

# dead code removed: 2026-06-12, unreachable block after return (原28-129行)

# ── 图表函数 ──────────────────────────────────

def _gen_kitchin_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib.dates as mdates
    setup_chart_font()

    STAGE_NAMES = {1: "主动去库存", 2: "被动去库存", 3: "主动补库存", 4: "被动补库存"}
    periods = [r["period"] for r in results]
    dates = [_p2date(p) for p in periods]
    demand_vals = [r.get("demand_yoy") for r in results]
    inventory_vals = [r.get("inventory_yoy") for r in results]
    ppi_vals = [r.get("pmi") for r in results]
    real_inv_vals = [r.get("real_inventory_yoy") for r in results]
    pmi_vals = [r.get("pmi") for r in results]
    m2_vals = [r.get("m2_yoy") for r in results]
    stages = [r["stage"] for r in results]

    stage_colors = {1: "#e74c3c", 2: "#2ecc71", 3: "#f39c12", 4: "#3498db"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("基钦周期(库存周期)定位分析", fontsize=15, fontweight="bold", y=1.02)

    ax1 = axes[0, 0]
    ax1t = ax1.twinx()
    apply_phase_shading(ax1, dates, stages, stage_colors)
    vd = [(d, v) for d, v in zip(dates, demand_vals) if v is not None]
    if vd:
        ax1.plot([x[0] for x in vd], [x[1] for x in vd], color="#2c3e50", lw=1.8, marker=".", ms=2, label="工业增加值同比%")
    vi = [(d, v) for d, v in zip(dates, inventory_vals) if v is not None]
    if vi:
        ax1t.plot([x[0] for x in vi], [x[1] for x in vi], color="#e67e22", lw=1.8, marker=".", ms=2, label="产成品存货同比%")
    vri = [(d, v) for d, v in zip(dates, real_inv_vals) if v is not None]
    if vri:
        ax1t.plot([x[0] for x in vri], [x[1] for x in vri], color="#e67e22", lw=0.8, alpha=0.5, ls="--", label="实际库存")
    ax1.axhline(0, color="#888", lw=0.5, ls="--")
    ax1t.axhline(0, color="#888", lw=0.5, ls="--")
    ax1.set_ylabel("工业增加值同比%", color="#2c3e50")
    ax1t.set_ylabel("库存同比%", color="#e67e22")

    ax2 = axes[0, 1]
    vp = [(d, v) for d, v in zip(dates, pmi_vals) if v is not None]
    if vp:
        ax2.plot([x[0] for x in vp], [x[1] for x in vp], color="#27ae60", lw=1.5, marker=".", ms=2, label="制造业PMI")
    ax2.axhline(50, color="#e74c3c", lw=1, ls="--", alpha=0.7, label="荣枯线(50)")
    ax2.set_ylabel("PMI")
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True, alpha=0.3, ls="--", lw=0.5)
    ax2.set_title("PMI 制造业趋势")

    ax3 = axes[1, 0]
    ax3t = ax3.twinx()
    vri2 = [(d, v) for d, v in zip(dates, real_inv_vals) if v is not None]
    if vri2:
        ax3.plot([x[0] for x in vri2], [x[1] for x in vri2], color="#e67e22", lw=1.5, marker=".", ms=2, label="实际库存同比%")
    vpp = [(d, v) for d, v in zip(dates, ppi_vals) if v is not None]
    if vpp:
        ax3t.plot([x[0] for x in vpp], [x[1] for x in vpp], color="#8e44ad", lw=1.5, marker=".", ms=2, label="PPI指数")
    ax3.axhline(0, color="#888", lw=0.5, ls="--")
    ax3t.axhline(100, color="#888", lw=0.5, ls="--")
    ax3.set_ylabel("实际库存同比%", color="#e67e22")
    ax3t.set_ylabel("PPI指数", color="#8e44ad")

    ax4 = axes[1, 1]
    vm = [(d, v) for d, v in zip(dates, m2_vals) if v is not None]
    if vm:
        ax4.plot([x[0] for x in vm], [x[1] for x in vm], color="#2980b9", lw=1.5, marker=".", ms=2, label="M2同比%")
    ax4.set_ylabel("M2同比%", color="#2980b9")

    setup_date_axes(axes.flat)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_juglar_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib.dates as mdates
    from matplotlib.patches import Patch
    setup_chart_font()

    PHASE_NAMES = {1: "复苏期", 2: "繁荣期", 3: "衰退期", 4: "萧条期"}
    periods = [r["period"] for r in results]
    dates = [_p2date(p) for p in periods]
    equip = [r.get("fix_inv_yoy") for r in results]
    pmi = [r.get("pmi") for r in results]
    ppi = [r.get("ppi_yoy") for r in results]
    phases = [r["phase"] for r in results]

    phase_colors = {1: "#2ecc71", 2: "#f39c12", 3: "#e74c3c", 4: "#3498db"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("朱格拉周期(固定资本投资周期)定位分析", fontsize=15, fontweight="bold", y=1.02)

    ax1 = axes[0, 0]
    ax1t = ax1.twinx()
    apply_phase_shading(ax1, dates, phases, phase_colors)
    veq = [(d, v) for d, v in zip(dates, equip) if v is not None]
    if veq:
        ax1.plot([x[0] for x in veq], [x[1] for x in veq], color="#2c3e50", lw=2, marker=".", ms=3, label="固投同比%")
    ax1.axhline(0, color="#888", lw=0.5, ls="--")
    ax1.set_ylabel("固投同比%", color="#2c3e50")
    h1, l1 = ax1.get_legend_handles_labels()
    sh = [Patch(facecolor=phase_colors[s], alpha=0.3, label=PHASE_NAMES[s]) for s in [1, 2, 3, 4]]
    ax1.legend(h1 + sh, l1 + [PHASE_NAMES[s] for s in [1, 2, 3, 4]], loc="upper left", fontsize=7, ncol=2)
    ax1.grid(True, alpha=0.3, ls="--", lw=0.5)
    ax1.set_title("固投 (阶段着色)")

    ax2 = axes[0, 1]
    ax2t = ax2.twinx()
    vpp = [(d, v) for d, v in zip(dates, ppi) if v is not None]
    if vpp:
        ax2.plot([x[0] for x in vpp], [x[1] for x in vpp], color="#c0392b", lw=1.5, marker=".", ms=2, label="PPI指数")
    vpmi = [(d, v) for d, v in zip(dates, pmi) if v is not None]
    if vpmi:
        ax2t.plot([x[0] for x in vpmi], [x[1] for x in vpmi], color="#27ae60", lw=1.5, marker=".", ms=2, label="制造业PMI")
    ax2.axhline(100, color="#888", lw=0.5, ls="--")
    ax2t.axhline(50, color="#e74c3c", lw=1, ls="--", alpha=0.7)
    ax2.set_ylabel("PPI指数", color="#c0392b")
    ax2t.set_ylabel("PMI", color="#27ae60")
    ax2.grid(True, alpha=0.3, ls="--", lw=0.5)
    ax2.set_title("PPI vs PMI")

    ax3 = axes[1, 0]
    ax4 = axes[1, 1]
    ax4.text(0.5, 0.5, "数据源限制：详细固投分项\n（设备/制造业/新建/扩建/改建）\n需 NBS API，当前仅显示总量", ha="center", va="center", transform=ax4.transAxes, fontsize=10, color="#888")
    ax4.set_title("固投细项占位")

    setup_date_axes(axes.flat)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_kuznets_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib.dates as mdates
    setup_chart_font()

    PHASE_NAMES = {1: "复苏期", 2: "繁荣期", 3: "衰退期", 4: "萧条期"}
    periods = [r["period"] for r in results]
    dates = [_p2date(p) for p in periods]
    re_sale = [r.get("re_yoy") for r in results]
    pmi = [r.get("pmi") for r in results]
    phases = [r["phase"] for r in results]

    phase_colors = {1: "#2ecc71", 2: "#f39c12", 3: "#e74c3c", 4: "#3498db"}
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle("库兹涅茨周期(房地产周期)定位分析", fontsize=15, fontweight="bold", y=1.02)

    ax1 = axes[0]
    apply_phase_shading(ax1, dates, phases, phase_colors)
    vs = [(d, v) for d, v in zip(dates, re_sale) if v is not None]
    if vs:
        ax1.plot([x[0] for x in vs], [x[1] for x in vs], color="#2c3e50", lw=2, marker=".", ms=3, label="房地产开发投资累计增长%")
    ax1.axhline(0, color="#888", lw=0.5, ls="--")
    ax1.set_ylabel("累计增长%", color="#2c3e50")
    ax1.grid(True, alpha=0.3, ls="--", lw=0.5)
    ax1.set_title("房地产开发投资 (阶段着色)")

    ax2 = axes[1]
    vp = [(d, v) for d, v in zip(dates, pmi) if v is not None]
    if vp:
        ax2.plot([x[0] for x in vp], [x[1] for x in vp], color="#27ae60", lw=1.5, marker=".", ms=2, label="制造业PMI")
    ax2.axhline(50, color="#e74c3c", lw=1, ls="--", alpha=0.7, label="荣枯线(50)")
    ax2.set_ylabel("PMI")
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True, alpha=0.3, ls="--", lw=0.5)
    ax2.set_title("PMI 制造业趋势")

    setup_date_axes(axes.flat)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_kondratiev_chart(result: dict, vals: list, output_path: str):
    from matplotlib.patches import Patch
    setup_chart_font()

    years = result.get("years", [])
    pca1 = vals
    dp = result.get("dominant_period")
    ph = result.get("phase", 0)
    # 使用 phase_utils.KOND_RENAME 统一命名 + 描述性副标签
    phase_labels = {
        0: "未知",
        1: f"{KOND_RENAME[1]}(繁荣初期)",
        2: f"{KOND_RENAME[2]}(顶峰)",
        3: f"{KOND_RENAME[3]}(下降期)",
        4: f"{KOND_RENAME[4]}(谷底)",
    }
    phase_colors = {1: "#2ecc71", 2: "#f39c12", 3: "#e74c3c", 4: "#3498db"}

    fig, ax = plt.subplots(figsize=(14, 7))

    # Fill phase regions on top axis
    mu = float(np.mean(pca1))
    sigma = float(np.std(pca1))

    # Phase shading by slope
    for i in range(1, len(years)):
        y_slope = pca1[i] - pca1[i - 1]
        y_val = pca1[i]
        if y_val > mu and y_slope < 0:
            color = phase_colors.get(3, "#e74c3c")  # 衰退
            alpha = 0.15
        elif y_val < mu and y_slope < 0:
            color = phase_colors.get(4, "#3498db")  # 萧条
            alpha = 0.12
        elif y_val < mu and y_slope > 0:
            color = phase_colors.get(1, "#2ecc71")  # 回升
            alpha = 0.12
        else:
            color = phase_colors.get(2, "#f39c12")  # 繁荣
            alpha = 0.15
        ax.axvspan(years[i - 1], years[i], alpha=alpha, color=color)

    # PCA1 line
    ax.plot(years, pca1, "b-", lw=2, marker=".", ms=4, label="PCA综合指数(去趋势)")
    ax.axhline(mu, color="#888", lw=0.5, ls="--", alpha=0.6)
    ax.axhline(mu + sigma, color="#aaa", lw=0.5, ls=":", alpha=0.4)
    ax.axhline(mu - sigma, color="#aaa", lw=0.5, ls=":", alpha=0.4)
    ax.axvline(x=years[-1], color="gray", ls="--", alpha=0.5)

    # Annotate peaks/troughs
    from scipy.signal import argrelextrema
    peaks = argrelextrema(np.array(pca1), np.greater, order=4)[0]
    troughs = argrelextrema(np.array(pca1), np.less, order=4)[0]
    for p in peaks:
        ax.annotate(f"{years[p]}", (years[p], pca1[p]), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=7, color="orange", fontweight="bold")
    for t in troughs:
        ax.annotate(f"{years[t]}", (years[t], pca1[t]), xytext=(0, -12),
                    textcoords="offset points", ha="center", fontsize=7, color="blue", fontweight="bold")

    # Legend — 使用 KOND_RENAME 命名
    legend_patches = [
        Patch(facecolor=phase_colors[1], alpha=0.3, label=f"{KOND_RENAME[1]}(↑<μ)"),
        Patch(facecolor=phase_colors[2], alpha=0.3, label=f"{KOND_RENAME[2]}(↑>μ)"),
        Patch(facecolor=phase_colors[3], alpha=0.3, label=f"{KOND_RENAME[3]}(↓>μ)"),
        Patch(facecolor=phase_colors[4], alpha=0.3, label=f"{KOND_RENAME[4]}(↓<μ)"),
    ]
    ax.legend(handles=legend_patches, loc="upper left", fontsize=7, ncol=2)

    # Title and info
    title = f"康波周期 — PCA综合指数 (指标: {', '.join(result.get('indicators_used', []))})"
    if dp:
        title += f" | 主周期 ~{dp:.0f}年"
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("标准化得分")
    ax.set_xlabel("年份")
    ax.grid(True, alpha=0.3)

    info = (
        f"数据: 世界银行({result.get('year_range','?')})  PCA方差占比: {result.get('pca_variance_ratio',0)*100:.0f}%\n"
        f"当前: {phase_labels.get(ph, '未知')}  相位置信度: {result.get('phase_confidence',0):.2f}"
    )
    ax.text(0.02, 0.02, info, transform=ax.transAxes, fontsize=8, verticalalignment="bottom",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.6))

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

# ═══════════════════════════════════════════════════════════════
# NBS API 客户端 — 已抽取到 data/sources/nbs_client.py（权威版本）
# 此处不再内联重复副本。需要 NBS 功能请 from ..data.sources.nbs_client import ...
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# Kondratiev 可选算法
# ═══════════════════════════════════════════════════════════════

def _calc_kondratiev_wavelet() -> tuple[dict, list]:
    """Morlet 小波变换提取康波周期相位"""
    from ....shared.utils import compute_kondratiev as _ck

    result = _ck()
    pca1 = result.get("pca1", [])
    if not pca1 or len(pca1) < 10:
        return result, []

    years = result.get("years", [])
    arr = np.asarray(pca1, dtype=np.float64)
    n = len(arr)

    scales = np.linspace(2, min(n // 2, 128), 50)
    power = np.zeros(len(scales))
    phase_at_end = np.zeros(len(scales))
    all_coefs = []

    for i, scale in enumerate(scales):
        f0 = 1.0 / scale
        sigma = scale / 3.0
        half = int(scale * 2)
        t = np.arange(-half, half + 1)
        kernel = np.exp(2j * np.pi * f0 * t) * np.exp(-t**2 / (2 * sigma**2))
        kernel = kernel / max(np.sqrt(np.sum(np.abs(kernel)**2)), 1e-30)
        conv = np.convolve(arr, kernel.conj()[::-1], mode="same")
        power[i] = np.sum(np.abs(conv)**2)
        phase_at_end[i] = np.angle(conv[-1])
        all_coefs.append(conv)

    valid = scales > 1
    s = scales[valid]
    p = power[valid]
    ph = phase_at_end[valid]
    peak_idx = np.argmax(p)

    dominant_period = float(s[peak_idx])
    dominant_angle = float(ph[peak_idx])
    normalized = dominant_angle % (2 * np.pi)

    if 0 <= normalized < np.pi / 2:
        phase = 1
    elif np.pi / 2 <= normalized < np.pi:
        phase = 2
    elif np.pi <= normalized < 3 * np.pi / 2:
        phase = 3
    else:
        phase = 4

    confidence = min(1.0, p[peak_idx] / max(p) if max(p) > 0 else 0.0)

    cycle_comp = np.real(all_coefs[peak_idx]).tolist()

    # 相位重映射到机构标准
    phase = phase % 4 + 1 if phase in (1, 2, 3, 4) else phase

    return {
        "dominant_period": round(dominant_period, 2),
        "phase": phase,
        "confidence": round(confidence, 4),
        "method_used": "wavelet_morlet",
        "year_range": f"{years[0]}~{years[-1]}" if years else "?",
        "pca_variance_ratio": result.get("pca_variance_ratio", 0),
        "indicators_used": result.get("indicators_used", []),
        "pca1": pca1,
        "years": years,
        "phase_confidence": round(confidence, 4),
        "turning_probability": 0.0,
        "all_results": {},
        # 全球/中国双线
        "global_zscore": result.get("global_zscore", []),
        "china_zscore": result.get("china_zscore", []),
        "global_cf_cycle": result.get("global_cf_cycle", []),
        "china_cf_cycle": result.get("china_cf_cycle", []),
        "global_phase": result.get("global_phase", 0),
        "global_phase_name": result.get("global_phase_name", "未知"),
        "global_confidence": result.get("global_confidence", 0),
        "china_phase": result.get("china_phase", 0),
        "china_phase_name": result.get("china_phase_name", "未知"),
        "china_confidence": result.get("china_confidence", 0),
        "china_pca1": result.get("china_pca1", []),
        "zscore": result.get("zscore", []),
        "cf_cycle": result.get("cf_cycle", []),
    }, cycle_comp

def _calc_kondratiev_bandpass() -> tuple[dict, list]:
    """Butterworth 40-60 年带通滤波提取康波相位"""
    from ....shared.utils import compute_kondratiev as _ck
    from ....shared.spectral import phase_from_waveform
    from scipy.signal import butter, sosfiltfilt

    result = _ck()
    pca1 = result.get("pca1", [])
    if not pca1 or len(pca1) < 20:
        return result, []

    years = result.get("years", [])
    arr = np.asarray(pca1, dtype=np.float64)
    n = len(arr)

    low = 1.0 / max(60, n * 0.6)
    high = 1.0 / 30
    sos = butter(2, [low, high], btype="band", output="sos", fs=1.0)
    filtered = sosfiltfilt(sos, arr)

    phase_info = phase_from_waveform(filtered.tolist(), current_idx=-1)
    # 相位重映射到机构标准
    ph = phase_info["phase"]
    phase_info["phase"] = ph % 4 + 1 if ph in (1, 2, 3, 4) else ph

    zc = np.where(np.diff(np.sign(filtered)))[0]
    if len(zc) > 2:
        avg_period = float(np.mean(np.diff(zc)) * 2)
    else:
        avg_period = None

    return {
        "dominant_period": round(avg_period, 1) if avg_period else None,
        "phase": phase_info["phase"],
        "confidence": round(phase_info["confidence"], 4),
        "method_used": "bandpass_40_60",
        "year_range": f"{years[0]}~{years[-1]}" if years else "?",
        "pca_variance_ratio": result.get("pca_variance_ratio", 0),
        "indicators_used": result.get("indicators_used", []),
        "pca1": pca1,
        "years": years,
        "phase_confidence": round(phase_info["confidence"], 4),
        "turning_probability": round(phase_info["turning_probability"], 4),
        "all_results": {},
        # 全球/中国双线
        "global_zscore": result.get("global_zscore", []),
        "china_zscore": result.get("china_zscore", []),
        "global_cf_cycle": result.get("global_cf_cycle", []),
        "china_cf_cycle": result.get("china_cf_cycle", []),
        "global_phase": result.get("global_phase", 0),
        "global_phase_name": result.get("global_phase_name", "未知"),
        "global_confidence": result.get("global_confidence", 0),
        "china_phase": result.get("china_phase", 0),
        "china_phase_name": result.get("china_phase_name", "未知"),
        "china_confidence": result.get("china_confidence", 0),
        "china_pca1": result.get("china_pca1", []),
        "zscore": result.get("zscore", []),
        "cf_cycle": result.get("cf_cycle", []),
    }, filtered.tolist()


# ═══════════════════════════════════════════════════════════════
# 三周期 FRED 扩展计算
# ═══════════════════════════════════════════════════════════════

def _fetch_fred_series(cache_key: str) -> tuple[list[str], list[float]]:
    """DB-first 拉取 FRED 序列，未入库则实时拉取并持久化"""
    from ....shared.cycle_db import get as db_get, set as db_set
    from ....data.sources.fred import get as fred_get
    # 1. DB 缓存（永久存储，不设过期）
    df = db_get(cache_key)
    if df is not None and not df.empty:
        return df["date"].tolist(), [float(v) if v is not None and not np.isnan(v) else None for v in df["value"]]
    # 2. 实时拉取并入库
    raw = fred_get(cache_key)
    if not raw:
        return [], []
    dates = [r[0][:10] for r in raw]
    vals = [r[1] for r in raw]
    try:
        db_set(cache_key, dates, vals)
    except Exception:
        pass
    return dates, vals


def _annualize(dates: list[str], vals: list[float]) -> tuple[list[str], list[float]]:
    """月频→年频：取每年最后一个非空值"""
    by_year: dict[str, float] = {}
    for d, v in zip(dates, vals):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        y = d[:4]
        by_year[y] = v
    years = sorted(by_year.keys())
    return years, [by_year[y] for y in years]


def _pct_change_yearly(years: list[str], vals: list[float]) -> tuple[list[str], list[float]]:
    """计算年增长率"""
    out_years, out_vals = [], []
    for i in range(1, len(vals)):
        prev, cur = vals[i - 1], vals[i]
        if prev is None or cur is None or prev == 0:
            continue
        out_years.append(years[i])
        out_vals.append((cur - prev) / abs(prev))
    return out_years, out_vals


def _compute_extended_cycle(
    indicators: list[tuple[str, float]],
    bandpass_lo: float,
    bandpass_hi: float,
    phase_type: str = "macro",
) -> tuple[dict, list[dict]]:
    """通用 FRED 扩展周期计算框架

    Args:
        indicators: [(cache_key, weight), ...] — FRED 序列及权重
        bandpass_lo: CF 带通低频边界（年）
        bandpass_hi: CF 带通高频边界（年）
        phase_type: "kitchin" / "macro" / "kond"

    Returns:
        (summary_dict, rows_list)
    """
    from ....shared.spectral import cf_bandpass
    from ....shared.phase_utils import get_phase_signal, get_phase_name

    # 1. 拉取所有指标
    raw_series: dict[str, tuple[list[str], list[float]]] = {}
    for key, _ in indicators:
        dates, vals = _fetch_fred_series(key)
        if dates:
            raw_series[key] = _annualize(dates, vals)

    if len(raw_series) < 2:
        return {"error": "insufficient_data", "method_used": "fred_extended"}, []

    # 2. 对齐年份
    all_years = set()
    for years, _ in raw_series.values():
        all_years.update(years)
    all_years = sorted(all_years)

    # 3. 增长率标准化
    normalized: dict[str, dict[str, float]] = {}
    for key, (years, vals) in raw_series.items():
        _, growth = _pct_change_yearly(years, vals)
        if not growth:
            continue
        year_to_g = {y: g for y, g in zip(years[1:], growth)}
        arr = np.array([year_to_g.get(y) for y in all_years], dtype=float)
        mask = ~np.isnan(arr)
        if mask.sum() < 10:
            continue
        mean, std = arr[mask].mean(), arr[mask].std()
        if std < 1e-12:
            continue
        z = (arr - mean) / std
        normalized[key] = {y: float(z[i]) if not np.isnan(z[i]) else None for i, y in enumerate(all_years)}

    if len(normalized) < 2:
        return {"error": "insufficient_normalized", "method_used": "fred_extended"}, []

    # 4. 加权合成
    weights = {key: w for key, w in indicators if key in normalized}
    composite: dict[str, float | None] = {}
    for y in all_years:
        vals = [normalized[k].get(y) for k in weights]
        ws = [weights[k] for k in weights if normalized[k].get(y) is not None]
        vs = [normalized[k][y] * weights[k] for k in weights if normalized[k].get(y) is not None]
        if vs:
            composite[y] = sum(vs) / sum(ws)
        else:
            composite[y] = None

    # 5. CF 带通滤波
    comp_vals = [composite.get(y) for y in all_years]
    clean = [v for v in comp_vals if v is not None]
    if len(clean) < 15:
        return {"error": "insufficient_for_bandpass", "method_used": "fred_extended"}, []

    try:
        bp = cf_bandpass(clean, low_yr=bandpass_lo, high_yr=bandpass_hi, ma_yr=None, fs=1.0)
        zs = bp["zscore"]
        cycle = bp["cycle"]
    except Exception:
        zs = _simple_zscore(clean)
        cycle = clean

    # 6. 映射回年份
    rows = []
    j = 0
    for i, y in enumerate(all_years):
        if comp_vals[i] is None:
            continue
        row = {"period": str(y), "composite_z": round(zs[j], 4) if j < len(zs) else None}
        # 相位判定：level + momentum
        z = zs[j] if j < len(zs) else 0
        mom = zs[j] - zs[j - 1] if j > 0 and j < len(zs) else 0
        if abs(mom) < 0.01 and j > 1:
            mom = zs[j] - zs[max(0, j - 3)]
        if mom > 0 and z < 0:
            phase = 1
        elif mom > 0 and z >= 0:
            phase = 2
        elif mom < 0 and z >= 0:
            phase = 3
        elif mom < 0 and z < 0:
            phase = 4
        else:
            phase = 0
        row["phase"] = phase
        row["phase_name"] = get_phase_name(phase, phase_type)
        row["cycle_signal"] = get_phase_signal(phase)
        row["cycle_val"] = round(cycle[j], 4) if j < len(cycle) else None
        rows.append(row)
        j += 1

    # 7. 汇总
    last = rows[-1] if rows else {}
    return {
        "phase": last.get("phase", 0),
        "phase_name": last.get("phase_name", "未知"),
        "confidence": round(min(1.0, len(clean) / 60), 4),
        "dominant_period": round((bandpass_lo + bandpass_hi) / 2, 1),
        "year_range": f"{all_years[0]}~{all_years[-1]}" if all_years else "?",
        "method_used": "fred_extended",
        "indicators_used": [k for k in weights],
        "pca_variance_ratio": 0,
        "turning_probability": 0,
    }, rows


# ── 三周期扩展入口 ──────────────────────────────────────

def compute_kitchin_extended() -> tuple[dict, list[dict]]:
    """基钦周期 FRED 扩展版 (1919~) — 工业生产+库存交叉法"""
    return _compute_extended_cycle(
        indicators=[
            ("fred_indpro", 0.5),       # 工业生产（需求代理）
            ("fred_mnfrir", 0.3),       # 制造商库存
            ("fred_m2sl", 0.2),         # M2 货币供应
        ],
        bandpass_lo=3,
        bandpass_hi=5,
        phase_type="kitchin",
    )


def compute_juglar_extended() -> tuple[dict, list[dict]]:
    """朱格拉周期 FRED 扩展版 (1929~) — 固定投资+设备投资"""
    return _compute_extended_cycle(
        indicators=[
            ("fred_pnfi", 0.4),         # 非住宅固定投资（设备代理）
            ("fred_fpi", 0.3),          # 私人固定投资
            ("fred_gnpca", 0.2),        # 实际 GNP
            ("fred_mcumfn", 0.1),       # 产能利用率
        ],
        bandpass_lo=7,
        bandpass_hi=12,
        phase_type="macro",
    )


def compute_kuznets_extended() -> tuple[dict, list[dict]]:
    """库兹涅茨周期 FRED 扩展版 (1947~) — 房价+住宅投资+开工"""
    return _compute_extended_cycle(
        indicators=[
            ("fred_ussthpi", 0.4),      # 美国房价指数
            ("fred_houst", 0.25),        # 新屋开工
            ("fred_prfi", 0.2),          # 住宅固定投资
            ("fred_indpro", 0.15),       # 工业生产（辅助）
        ],
        bandpass_lo=14,
        bandpass_hi=25,
        phase_type="macro",
    )
