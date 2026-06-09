"""Kondratiev wave analysis"""
import json
import logging
from datetime import datetime
from pathlib import Path

import matplotlib;
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
def _compute_kondratiev(method: str = "pca"):
    method = method.lower()
    if method == "wavelet":
        return _calc_kondratiev_wavelet()
    elif method == "bandpass":
        return _calc_kondratiev_bandpass()
    from DeepFusion.deep_fusion.shared.utils import compute_kondratiev as _ck

    result = _ck()
    if not result.get("pca1"):
        return result, []
    return result, result["pca1"]


    # Fetch actual data ranges via cached _nbs() wrapper
    from DeepFusion.deep_fusion.shared.utils import fetch_wb

    coverage = []

    # Kitchin: NBS indicators
    def _safe_range(fn):
        try:
            p, v = fn()
            if p:
                return p[0], p[-1]
        except Exception:
            pass
        return ("?", "?")

    ind_yoy = IndicatorDef(key="_", fetch_fn=_fetch_nbs_ind_yoy)
    inv_yoy = IndicatorDef(key="_", fetch_fn=_fetch_nbs_inventory_yoy)
    fix_inv = IndicatorDef(key="_", fetch_fn=_fetch_nbs_fix_inv_monthly)
    re_dev = IndicatorDef(key="_", fetch_fn=_fetch_nbs_re_dev_yoy)

    s1, e1 = _safe_range(ind_yoy.fetch)
    coverage.append(("基钦: 工业增加值", 2000 if s1 == "?" else int(s1[:4]), 2026, "#2ecc71"))
    s2, e2 = _safe_range(_fetch_nbs_inventory_yoy)
    coverage.append(("基钦: 产成品库存", 2018 if s2 == "?" else int(s2[:4]), 2026, "#27ae60"))
    s3, e3 = _safe_range(fix_inv.fetch)
    coverage.append(("基钦: 固投(辅)", 2000 if s3 == "?" else int(s3[:4]), 2026, "#1abc9c"))
    coverage.append(("基钦: PMI", 2005, 2026, "#e67e22"))
    coverage.append(("基钦: M2", 2000, 2026, "#f39c12"))

    # Juglar
    coverage.append(("朱格拉: 固投", 2000 if s3 == "?" else int(s3[:4]), 2026, "#3498db"))
    s1j, e1j = _safe_range(ind_yoy.fetch)
    coverage.append(("朱格拉: 工业增加值", 2000 if s1j == "?" else int(s1j[:4]), 2026, "#2980b9"))
    coverage.append(("朱格拉: PPI", 2011, 2026, "#9b59b6"))
    coverage.append(("朱格拉: PMI", 2005, 2026, "#8e44ad"))

    # Kuznets
    s1k, e1k = _safe_range(re_dev.fetch)
    coverage.append(("库兹涅茨: 房地产投资", 2000 if s1k == "?" else int(s1k[:4]), 2026, "#e74c3c"))
    coverage.append(("库兹涅茨: PMI", 2005, 2026, "#c0392b"))

    # Kondratiev (WB uses CacheKey internally)
    for lbl, ind in [
        ("康波: 人均GDP", "NY.GDP.PCAP.KD"),
        ("康波: 人口", "SP.POP.TOTL"),
        ("康波: 城镇化率", "SP.URB.TOTL"),
        ("康波: 通胀(GDP平减)", "NY.GDP.DEFL.KD.ZG"),
        ("康波: GDP增速", "NY.GDP.MKTP.KD.ZG"),
    ]:
        vals = fetch_wb(ind)
        if vals:
            coverage.append((lbl, vals[0][0], vals[-1][0], "#8B4513"))
        else:
            coverage.append((lbl, 1960, 2024, "#8B4513"))

    # Sort: Kondratiev first, then Kuznets, Juglar, Kitchin
    cycle_order = {"康波": 0, "库兹涅茨": 1, "朱格拉": 2, "基钦": 3}
    coverage.sort(key=lambda x: (cycle_order.get(x[0].split(":")[0], 9), x[0]))

    fig, ax = plt.subplots(figsize=(14, max(6, len(coverage) * 0.35)))
    fig.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.08)
    current_year = 2026

    for i, (label, start, end, color) in enumerate(coverage):
        end_actual = min(end, current_year)
        if end_actual < start:
            continue
        ax.barh(i, end_actual - start, left=start, height=0.6, color=color, alpha=0.8, edgecolor="white", linewidth=0.5)
        # Label on bar
        bar_label = f"{start}-{end_actual}"
        if end != current_year and end < current_year:
            bar_label += f" (截{end})"
        ax.text(end_actual - 0.3, i, bar_label, va="center", ha="right", fontsize=6, color="white", fontweight="bold")

    ax.set_yticks(range(len(coverage)))
    ax.set_yticklabels([c[0] for c in coverage], fontsize=8)
    ax.set_xlabel("年份", fontsize=10)
    ax.set_title("经济周期分析 — 数据覆盖甘特图", fontsize=13, fontweight="bold")
    ax.axvline(x=current_year, color="red", ls="--", lw=1, alpha=0.5)
    ax.text(current_year, len(coverage) - 0.5, " 当前", color="red", fontsize=8, va="bottom")
    ax.set_xlim(left=1955)
    ax.grid(True, axis="x", alpha=0.3)

    # Add cycle group labels
    cycle_groups = {"康波": (0, 999), "库兹涅茨": (999, 999), "朱格拉": (999, 999), "基钦": (999, 999)}
    for i, (label, _, _, _) in enumerate(coverage):
        prefix = label.split(":")[0]
        if prefix in cycle_groups:
            s, e = cycle_groups[prefix]
            cycle_groups[prefix] = (min(s, i), max(e, i))

    y_pos = len(coverage)
    for prefix, (s, e) in sorted(cycle_groups.items(), key=lambda x: x[1][0]):
        if e >= s:
            mid = (s + e) / 2
            ax.annotate(prefix, xy=(0.01, mid), xycoords=("axes fraction", "data"),
                        fontsize=10, fontweight="bold", ha="left", va="center",
                        rotation=0, color="#555")

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

# ── 图表函数 ──────────────────────────────────

def _gen_kitchin_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm

    _font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for _p in _font_paths:
        if Path(_p).exists():
            _fp = fm.FontProperties(fname=_p)
            plt.rcParams["font.family"] = _fp.get_name()
            break

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
    current_stage = None
    stage_start = 0
    sr = []
    for i, s in enumerate(stages + [0]):
        if s != current_stage:
            if current_stage is not None and current_stage != 0:
                sr.append((stage_start, i, current_stage))
            current_stage = s
            stage_start = i
        if i == len(stages):
            break
    for ss, se, s in sr:
        ax1.axvspan(dates[ss], dates[min(se, len(dates) - 1)], alpha=0.12, color=stage_colors.get(s, "#ccc"))
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

    for ax in axes.flat:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", rotation=45, labelsize=8)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_juglar_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Patch
    import matplotlib.font_manager as fm

    _font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for _p in _font_paths:
        if Path(_p).exists():
            _fp = fm.FontProperties(fname=_p)
            plt.rcParams["font.family"] = _fp.get_name()
            break

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
    current_p = None
    ps_start = 0
    sr = []
    for i, s in enumerate(phases + [0]):
        if s != current_p:
            if current_p is not None and current_p != 0:
                sr.append((ps_start, i, current_p))
            current_p = s
            ps_start = i
        if i == len(phases):
            break
    for ss, se, s in sr:
        ax1.axvspan(dates[ss], dates[min(se, len(dates) - 1)], alpha=0.12, color=phase_colors.get(s, "#ccc"))
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

    for ax in axes.flat:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", rotation=45, labelsize=8)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_kuznets_chart(results: list[dict], data: dict, output_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm

    _font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for _p in _font_paths:
        if Path(_p).exists():
            _fp = fm.FontProperties(fname=_p)
            plt.rcParams["font.family"] = _fp.get_name()
            break

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
    current_p = None
    ps_start = 0
    sr = []
    for i, s in enumerate(phases + [0]):
        if s != current_p:
            if current_p is not None and current_p != 0:
                sr.append((ps_start, i, current_p))
            current_p = s
            ps_start = i
        if i == len(phases):
            break
    for ss, se, s in sr:
        ax1.axvspan(dates[ss], dates[min(se, len(dates) - 1)], alpha=0.12, color=phase_colors.get(s, "#ccc"))
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

    for ax in axes.flat:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", rotation=45, labelsize=8)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

def _gen_kondratiev_chart(result: dict, vals: list, output_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import matplotlib.font_manager as fm

    _font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for _p in _font_paths:
        if Path(_p).exists():
            _fp = fm.FontProperties(fname=_p)
            plt.rcParams["font.family"] = _fp.get_name()
            break

    years = result.get("years", [])
    pca1 = vals
    dp = result.get("dominant_period")
    ph = result.get("phase", 0)
    phase_labels = ["未知", "复苏(繁荣初期)", "繁荣(顶峰)", "衰退(下降期)", "萧条(谷底)"]
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
            color = phase_colors.get(1, "#2ecc71")  # 复苏
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

    # Legend
    legend_patches = [
        Patch(facecolor=phase_colors[1], alpha=0.3, label="复苏期(↑<μ)"),
        Patch(facecolor=phase_colors[2], alpha=0.3, label="繁荣期(↑>μ)"),
        Patch(facecolor=phase_colors[3], alpha=0.3, label="衰退期(↓>μ)"),
        Patch(facecolor=phase_colors[4], alpha=0.3, label="萧条期(↓<μ)"),
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
        f"当前: {phase_labels[ph]}  相位置信度: {result.get('phase_confidence',0):.2f}"
    )
    ax.text(0.02, 0.02, info, transform=ax.transAxes, fontsize=8, verticalalignment="bottom",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.6))

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

# ═══════════════════════════════════════════════════════════════
# NBS API 客户端 — 内联自 workspace/cycles/scripts/nbs_client.py
# 国家统计局新版 API V2.0
# 三步走: 搜索→cid → queryIndicatorsByCid → indicatorId → getEsDataByCidAndDt → 数据
# ═══════════════════════════════════════════════════════════════

_NBS_BASE_URL = "https://data.stats.gov.cn/dg/website/publicrelease/web/external"
_NBS_ROOT_IDS = {
    1: "fc982599aa684be7969d7b90b1bd0e84",
    2: "a94b8b7365a94874968cabbe392cf679",
    3: "1dcdcab5f2c6476aa8cd5e5dca351159",
}
_NBS_CACHE_DIR = Path.home() / ".cache" / "deep_fusion" / "nbs"
_NBS_REQUEST_INTERVAL = 0.6

class _NbsClient:
    __shared: "_NbsClient | None" = None

    def __new__(cls, *args, **kwargs):
        if cls.__shared is None:
            cls.__shared = super().__new__(cls)
        return cls.__shared

    def __init__(self, cid_dir: str | Path | None = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.cache_dir = _NBS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self._session.trust_env = False
        self._last_request = 0.0
        self._cid_index: list[dict] | None = None
        self._cid_dir = Path(cid_dir) if cid_dir else (Path(__file__).resolve().parent.parent / "shared" / "data")

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < _NBS_REQUEST_INTERVAL:
            time.sleep(_NBS_REQUEST_INTERVAL - elapsed)
        self._last_request = time.time()

    def _cache_get(self, key: str, ttl: int) -> dict | None:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            age = time.time() - path.stat().st_mtime
            if age < ttl:
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _cache_set(self, key: str, data):
        path = self.cache_dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")

    def _load_cid_index(self):
        if self._cid_index is not None:
            return
        self._cid_index = []
        for fname in ["nbs_cids_monthly.json", "nbs_cids_quarterly.json", "nbs_cids_annual.json"]:
            path = self._cid_dir / fname
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                freq = "月度" if "monthly" in fname else ("季度" if "quarterly" in fname else "年度")
                for item in data:
                    self._cid_index.append({
                        "cid": item.get("id", ""),
                        "name": item.get("name", ""),
                        "freq": freq,
                        "sdate": item.get("sdate"),
                        "edate": item.get("edate"),
                        "treeinfo_globalid": item.get("treeinfo_globalid", ""),
                    })

    def search(self, keyword: str, freq: str = "") -> list[dict]:
        self._load_cid_index()
        if self._cid_index is None:
            return []
        results = []
        for item in self._cid_index:
            if keyword in item["name"]:
                if freq and item["freq"] != freq:
                    continue
                results.append(dict(item))
        return results

    def get_tree_children(self, pid: str = "", code: str = "1") -> list[dict]:
        self._rate_limit()
        resp = self._session.get(
            f"{_NBS_BASE_URL}/new/queryIndexTreeAsync",
            params={"pid": pid, "code": code},
            timeout=15,
        )
        nodes = resp.json().get("data", [])
        results = []
        for node in nodes:
            results.append({
                "cid": node.get("_id", ""),
                "name": node.get("name", ""),
                "isLeaf": node.get("isLeaf", False),
                "sdate": node.get("sdate"),
                "edate": node.get("edate"),
                "treeinfo_globalid": node.get("treeinfo_globalid", ""),
            })
        return results

    def find_cid_by_path(self, path: list[str], code: str = "1") -> str | None:
        pid = ""
        current = self.get_tree_children(pid, code)
        for segment in path:
            matched = [n for n in current if segment in n["name"]]
            if not matched:
                return None
            node = matched[0]
            if node["isLeaf"] or segment == path[-1]:
                return node["cid"]
            pid = node["cid"]
            current = self.get_tree_children(pid, code)
        return None

    def get_indicators(self, cid: str, use_cache: bool = True) -> list[dict]:
        cache_key = f"indicators_{cid}"
        if use_cache:
            cached = self._cache_get(cache_key, ttl=86400)
            if cached:
                return cached
        self._rate_limit()
        resp = self._session.get(
            f"{_NBS_BASE_URL}/new/queryIndicatorsByCid",
            params={"cid": cid},
            timeout=15,
        )
        data = resp.json()
        if not data.get("success"):
            return []
        indicators = data["data"].get("list", [])
        self._cache_set(cache_key, indicators)
        return indicators

    def find_indicator(self, cid: str, keyword: str, use_cache: bool = True) -> dict | None:
        indicators = self.get_indicators(cid, use_cache=use_cache)
        for ind in indicators:
            if keyword in ind.get("i_showname", ""):
                return ind
        return None

    def find_indicators(self, cid: str, keyword: str, use_cache: bool = True) -> list[dict]:
        indicators = self.get_indicators(cid, use_cache=use_cache)
        return [ind for ind in indicators if keyword in ind.get("i_showname", "")]

    def fetch_data(
        self,
        cid: str,
        indicator_ids: list[str],
        start: str = "2020",
        end: str = "",
        region: list[dict] | None = None,
        freq: str = "MM",
    ) -> pd.DataFrame:
        if region is None:
            region = [{"text": "全国", "value": "000000000000"}]
        if not end:
            end = datetime.now().strftime("%Y%m")
            if freq == "SS":
                yyyy = int(end[:4])
                q = (int(end[4:6]) - 1) // 3 + 1
                end = f"{yyyy}{q:02d}"
            elif freq == "YY":
                end = end[:4]
        suffix = {"MM": "MM", "SS": "SS", "YY": "YY"}.get(freq, "MM")
        dt_range = f"{start}01{suffix}-{end}{suffix}"
        root_id = _NBS_ROOT_IDS.get({"MM": 1, "SS": 2, "YY": 3}.get(freq, 1), _NBS_ROOT_IDS[1])
        payload = {
            "cid": cid,
            "indicatorIds": indicator_ids,
            "das": region,
            "dts": [dt_range],
            "showType": "1",
            "rootId": root_id,
        }
        self._rate_limit()
        resp = self._session.post(
            f"{_NBS_BASE_URL}/getEsDataByCidAndDt",
            json=payload,
            timeout=30,
        )
        data = resp.json()
        if not data.get("success"):
            raise Exception(f"NBS API 失败: {data.get('message', '未知错误')}")
        records = data.get("data", [])
        if not records:
            return pd.DataFrame()
        rows = []
        for rec in records:
            row = {"period": rec.get("code", ""), "period_name": rec.get("name", "")}
            for val in rec.get("values", []):
                col_name = val.get("i_showname", val.get("_id", ""))
                row[col_name] = val.get("value")
                if "i_mark" not in row and val.get("i_mark"):
                    row["_口径_"] = val["i_mark"]
            rows.append(row)
        df = pd.DataFrame(rows)
        for col in df.columns:
            if col in ("period", "period_name", "_口径_"):
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def fetch_merged(
        self,
        cid_indicator_pairs: list[tuple[str, str]],
        cid_date_ranges: list[tuple[str | None, str | None]] | None = None,
        start: str = "2000",
        end: str = "",
        freq: str = "MM",
    ) -> pd.DataFrame:
        all_frames = []
        for i, (cid, ind_id) in enumerate(cid_indicator_pairs):
            df = self.fetch_data(cid, [ind_id], start=start, end=end, freq=freq)
            if df is not None and not df.empty:
                val_cols = [c for c in df.columns if c not in ("period", "period_name", "_口径_")]
                if val_cols:
                    df = df[["period"] + val_cols]
                    sdate = cid_date_ranges[i][0] if cid_date_ranges else None
                    edate = cid_date_ranges[i][1] if cid_date_ranges else None
                    df["_sdate"] = sdate or ""
                    df["_edate"] = edate or ""
                    all_frames.append(df)
        if not all_frames:
            return pd.DataFrame()
        stacked = pd.concat(all_frames, ignore_index=True)
        val_col = [c for c in stacked.columns if c not in ("period", "_sdate", "_edate")][0]
        periods = sorted(stacked["period"].unique())
        rows = []
        for p in periods:
            subset = stacked[stacked["period"] == p]
            if subset.empty:
                continue
            candidates = []
            for _, row in subset.iterrows():
                v = row[val_col]
                if pd.isna(v):
                    continue
                sd = str(row["_sdate"]).strip()
                ed = str(row["_edate"]).strip()
                p_num = int(str(p)[:6])
                in_range = True
                if sd and sd != "None":
                    in_range = in_range and p_num >= int(sd.replace("-", "")[:6])
                if ed and ed != "None" and str(ed) != "None":
                    in_range = in_range and p_num <= int(ed.replace("-", "")[:6])
                candidates.append((v, in_range, sd, ed))
            if candidates:
                valid = [c for c in candidates if c[1]]
                if valid:
                    rows.append({"period": p, val_col: valid[-1][0]})
                else:
                    rows.append({"period": p, val_col: candidates[0][0]})
        result = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["period", val_col])
        return result

    def search_and_fetch(
        self,
        keyword: str,
        indicator_keyword: str = "增减",
        start: str = "2000",
        end: str = "",
        freq: str = "MM",
    ) -> pd.DataFrame | None:
        candidates = self.search(keyword, freq={"MM": "月度", "SS": "季度", "YY": "年度"}.get(freq, ""))
        if not candidates:
            return None
        cid_infos = []
        for c in candidates:
            indicators = self.get_indicators(c["cid"])
            matched = [i for i in indicators if indicator_keyword in (i.get("i_showname") or "")]
            if matched:
                cid_infos.append({
                    "cid": c["cid"],
                    "name": c["name"],
                    "sdate": c.get("sdate"),
                    "edate": c.get("edate"),
                    "indicator": matched[0],
                })
        if not cid_infos:
            return None

        def _sort_key(x):
            s = x.get("sdate")
            return int(s) if s else 9999
        cid_infos.sort(key=_sort_key)
        pairs = [(ci["cid"], ci["indicator"]["_id"]) for ci in cid_infos]
        date_ranges = [(ci.get("sdate"), ci.get("edate")) for ci in cid_infos]
        return self.fetch_merged(pairs, cid_date_ranges=date_ranges, start=start, end=end, freq=freq)

    def clear_cache(self):
        for f in self.cache_dir.glob("*.json"):
            f.unlink()

    def cache_size(self) -> int:
        return sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))

def _get_nbs_client():
    return _NbsClient()

def _clean_df(df) -> tuple[list[str], list[float]]:
    if df is None or df.empty:
        return [], []
    periods = [p[:6] for p in df["period"].tolist()]
    val_col = [c for c in df.columns if c not in ("period",)][0]
    values = df[val_col].tolist()
    clean_p, clean_v = [], []
    for p, v in zip(periods, values):
        if v is not None and np.isfinite(v):
            clean_p.append(p)
            clean_v.append(float(v))
    return clean_p, clean_v

def _fetch_by_indicator_name(
    dataset_keyword: str,
    indicator_name: str,
    freq: str = "MM",
    start: str = "2000",
) -> pd.DataFrame | None:
    client = _get_nbs_client()
    cids = client.search(dataset_keyword)
    if not cids:
        return None
    cid_infos = []
    for c in cids:
        indicators = client.get_indicators(c["cid"])
        for ind in indicators:
            name = ind.get("i_showname", "")
            if name == indicator_name or name.startswith(indicator_name):
                cid_infos.append({
                    "cid": c["cid"],
                    "name": c["name"],
                    "sdate": c.get("sdate"),
                    "edate": c.get("edate"),
                    "indicator": ind,
                })
                break
    if not cid_infos:
        return None
    cid_infos.sort(key=lambda x: int(x.get("sdate") or 0) if x.get("sdate") and x["sdate"].lstrip("-").isdigit() else 9999)
    pairs = [(ci["cid"], ci["indicator"]["_id"]) for ci in cid_infos]
    date_ranges = [(ci.get("sdate"), ci.get("edate")) for ci in cid_infos]
    return client.fetch_merged(pairs, cid_date_ranges=date_ranges, start=start, end="", freq=freq)

def _fetch_nbs_inventory_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("产成品存货", "增减"))

def _fetch_nbs_ind_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("规上工业增加值增长速度", "同比增长"))

def _fetch_nbs_fix_inv_monthly() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("固定资产投资概况", "累计增长"))

def _fetch_nbs_re_dev_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("房地产开发投资情况", "累计增长"))

def _fetch_nbs_cpi_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_fetch_by_indicator_name(
        "全国居民消费价格分类指数 (上年同月=100)",
        "居民消费价格指数 (上年同月=100)",
    ))

def _fetch_nbs_ppi_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_fetch_by_indicator_name(
        "工业生产者出厂价格指数 (上年同月=100)",
        "工业生产者出厂价格指数 (上年同月=100)",
    ))

def _fetch_nbs_gdp_quarterly() -> tuple[list[str], list[float]]:
    try:
        df = _fetch_by_indicator_name(
            "国内生产总值指数",
            "国内生产总值指数 (上年同期=100) 当季值",
            freq="SS",
        )
        if df is not None:
            val_col = [c for c in df.columns if c not in ("period",)][0]
            df[val_col] = df[val_col] - 100
        return _clean_df(df)
    except Exception:
        return [], []

def _fetch_nbs_unemployment() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("城镇调查失业率", "失业率"))

# ═══════════════════════════════════════════════════════════════
# Kondratiev 可选算法
# ═══════════════════════════════════════════════════════════════

def _calc_kondratiev_wavelet() -> tuple[dict, list]:
    """Morlet 小波变换提取康波周期相位"""
    from DeepFusion.deep_fusion.shared.utils import compute_kondratiev as _ck

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
    }, cycle_comp

def _calc_kondratiev_bandpass() -> tuple[dict, list]:
    """Butterworth 40-60 年带通滤波提取康波相位"""
    from DeepFusion.deep_fusion.shared.utils import compute_kondratiev as _ck
    from DeepFusion.deep_fusion.shared.spectral import phase_from_waveform
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
    }, filtered.tolist()


# ═══════════════════════════════════════════════════════════════
# 三周期 FRED 扩展计算
# ═══════════════════════════════════════════════════════════════

def _fetch_fred_series(cache_key: str) -> tuple[list[str], list[float]]:
    """DB-first 拉取 FRED 序列，未入库则实时拉取并持久化"""
    from DeepFusion.deep_fusion.shared.cycle_db import get as db_get, set as db_set
    from DeepFusion.deep_fusion.data.sources.fred import get as fred_get
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
    from DeepFusion.deep_fusion.shared.spectral import cf_bandpass
    from DeepFusion.deep_fusion.shared.phase_utils import get_phase_signal, get_phase_name

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


def _simple_zscore(vals: list[float]) -> list[float]:
    arr = np.array(vals, dtype=float)
    m, s = np.nanmean(arr), np.nanstd(arr)
    if s < 1e-12:
        return [0.0] * len(vals)
    return ((arr - m) / s).tolist()


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
