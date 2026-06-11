"""周期定位工具 — 基钦/朱格拉/库兹涅茨/康波
核心思路：一个 CycleEngine + 4 份配置表 → 4 套 @mcp.tool
分析层驻在 deep_fusion/analysis/macro/cycles/，tools/cycles.py 只做注册+胶水。
"""
import json
import logging
from typing import Any

from pydantic import Field

from ..analysis.macro.cycles import (
    CYCLES, CYCLE_METADATA,
    _compute, _make_report_fn,
    _make_chart_fn, )
# ── 分析层导入 ────────────────────────────────────────
from ..analysis.macro.cycles.kondratiev import (
    _compute_kondratiev, _gen_kondratiev_chart,
)
from ..cache import CacheKey
from ..server import mcp

logger = logging.getLogger(__name__)

# ── NBS fetch 函数导入 ────────────────────────────────
from ..data.sources.nbs_client import (
    _fetch_nbs_inventory_yoy, _fetch_nbs_ind_yoy, _fetch_nbs_fix_inv_monthly,
    _fetch_nbs_re_dev_yoy, _fetch_nbs_cpi_yoy, _fetch_nbs_ppi_yoy,
    _fetch_nbs_gdp_quarterly, _fetch_nbs_unemployment,
    _fetch_nbs_equip_invest, _fetch_nbs_manufacturing_invest,
    _fetch_nbs_re_sales_area, _fetch_nbs_re_new_start,
    _fetch_nbs_capacity_util, _fetch_house_price_yoy,
)

# ── FN_MAP — _nbs() 延迟解析用 ──────────────────────────
_FN_MAP: dict[str, Any] = {
    "fetch_nbs_inventory_yoy": _fetch_nbs_inventory_yoy,
    "fetch_nbs_ind_yoy": _fetch_nbs_ind_yoy,
    "fetch_nbs_fix_inv_monthly": _fetch_nbs_fix_inv_monthly,
    "fetch_nbs_re_dev_yoy": _fetch_nbs_re_dev_yoy,
    "fetch_nbs_cpi_yoy": _fetch_nbs_cpi_yoy,
    "fetch_nbs_ppi_yoy": _fetch_nbs_ppi_yoy,
    "fetch_nbs_gdp_quarterly": _fetch_nbs_gdp_quarterly,
    "fetch_nbs_unemployment": _fetch_nbs_unemployment,
    "fetch_nbs_equip_invest": _fetch_nbs_equip_invest,
    "fetch_nbs_manufacturing_invest": _fetch_nbs_manufacturing_invest,
    "fetch_nbs_re_sales_area": _fetch_nbs_re_sales_area,
    "fetch_nbs_re_new_start": _fetch_nbs_re_new_start,
    "fetch_nbs_capacity_util": _fetch_nbs_capacity_util,
    "fetch_house_price_yoy": _fetch_house_price_yoy,
    # 别名（短名兼容 original cycles.py 的 FN_MAP 调用）
    "fetch_ind_yoy": _fetch_nbs_ind_yoy,
    "fetch_inventory_yoy": _fetch_nbs_inventory_yoy,
    "fetch_fix_inv_monthly": _fetch_nbs_fix_inv_monthly,
    "fetch_re_dev_yoy": _fetch_nbs_re_dev_yoy,
    "fetch_cpi_yoy": _fetch_nbs_cpi_yoy,
    "fetch_ppi_yoy": _fetch_nbs_ppi_yoy,
    "fetch_gdp_quarterly": _fetch_nbs_gdp_quarterly,
    "fetch_unemployment": _fetch_nbs_unemployment,
    "fetch_equip_invest": _fetch_nbs_equip_invest,
    "fetch_manufacturing_invest": _fetch_nbs_manufacturing_invest,
    "fetch_re_sales_area": _fetch_nbs_re_sales_area,
    "fetch_re_new_start": _fetch_nbs_re_new_start,
    "fetch_capacity_util": _fetch_nbs_capacity_util,
    "fetch_house_price": _fetch_house_price_yoy,
}

# ============================================================
#  工具注册：基钦 / 朱格拉 / 库兹涅茨（循环生成）
# ============================================================
for _cid in ["kitchin", "juglar", "kuznets"]:
    _cfg = CYCLES[_cid]
    _meta = CYCLE_METADATA[_cid]

    # phase/direction/value keys（各周期不同）
    if _cid == "kitchin":
        _phase_key, _dir_key, _val_key = "stage", "demand_dir", "demand_yoy"
    elif _cid == "juglar":
        _phase_key, _dir_key, _val_key = "phase", "fix_dir", "comp_z"
    else:  # kuznets
        _phase_key, _dir_key, _val_key = "phase", "re_dir", "comp_z"

    _fn_report = _make_report_fn(_cid, _phase_key, _dir_key, _val_key, _cfg.name)
    mcp.tool(name=_meta["name"], description=_meta["desc"])(_fn_report)

    _fn_chart = _make_chart_fn(_cid)
    mcp.tool(name=_meta["chart_name"], description=_meta.get("chart_desc", f"生成{_cfg.name}分析图"))(_fn_chart)

# ── data_* 工具（返回 JSON 数据） ──────────────────────────
@mcp.tool(
    name="data_kitchin",
    description="获取基钦周期（库存周期）各阶段定位数据（JSON数组）",
)
def data_kitchin() -> str:
    _ck = CacheKey.init("cycles_data_kitchin", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    _, _, results = _compute("kitchin", limit=0)
    from ..shared.phase_utils import get_phase_signal, KITCHIN_PHASE_NAMES
    for r in results:
        stage = r.get("stage", 0)
        r["cycle_phase"] = stage
        r["cycle_phase_name"] = KITCHIN_PHASE_NAMES.get(stage, "未知")
        r["cycle_signal"] = get_phase_signal(stage)
    text = json.dumps(results, ensure_ascii=False)
    _ck.set(text)
    return text


@mcp.tool(
    name="data_juglar",
    description="获取朱格拉周期（固定资本投资周期）各阶段定位数据（JSON数组）",
)
def data_juglar() -> str:
    _ck = CacheKey.init("cycles_data_juglar", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    _, _, results = _compute("juglar", limit=0)
    from ..shared.phase_utils import get_phase_signal, MACRO_PHASE_NAMES
    for r in results:
        phase = r.get("phase", 0)
        r["cycle_phase"] = phase
        r["cycle_phase_name"] = MACRO_PHASE_NAMES.get(phase, "未知")
        r["cycle_signal"] = get_phase_signal(phase)
    text = json.dumps(results, ensure_ascii=False)
    _ck.set(text)
    return text


@mcp.tool(
    name="data_kuznets",
    description="获取库兹涅茨周期（房地产周期）各阶段定位数据（JSON数组）",
)
def data_kuznets() -> str:
    _ck = CacheKey.init("cycles_data_kuznets", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    _, _, results = _compute("kuznets", limit=0)
    from ..shared.phase_utils import get_phase_signal, MACRO_PHASE_NAMES
    for r in results:
        phase = r.get("phase", 0)
        r["cycle_phase"] = phase
        r["cycle_phase_name"] = MACRO_PHASE_NAMES.get(phase, "未知")
        r["cycle_signal"] = get_phase_signal(phase)
    text = json.dumps(results, ensure_ascii=False)
    _ck.set(text)
    return text


# ── FRED 扩展周期工具 ─────────────────────────────────────
@mcp.tool(
    name="data_kitchin_extended",
    description="基钦周期 FRED 扩展版（1919~），工业生产+制造商库存+M2，年频JSON数组",
)
def data_kitchin_extended() -> str:
    _ck = CacheKey.init("cycles_data_kitchin_extended_v1", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    from ..analysis.macro.cycles.kondratiev import compute_kitchin_extended
    _, rows = compute_kitchin_extended()
    text = json.dumps(rows, ensure_ascii=False)
    _ck.set(text)
    return text


@mcp.tool(
    name="data_juglar_extended",
    description="朱格拉周期 FRED 扩展版（1929~），非住宅固定投资+私人固投+GNP+产能利用率，年频JSON数组",
)
def data_juglar_extended() -> str:
    _ck = CacheKey.init("cycles_data_juglar_extended_v1", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    from ..analysis.macro.cycles.kondratiev import compute_juglar_extended
    _, rows = compute_juglar_extended()
    text = json.dumps(rows, ensure_ascii=False)
    _ck.set(text)
    return text


@mcp.tool(
    name="data_kuznets_extended",
    description="库兹涅茨周期 FRED 扩展版（1947~），美国房价+新屋开工+住宅投资，年频JSON数组",
)
def data_kuznets_extended() -> str:
    _ck = CacheKey.init("cycles_data_kuznets_extended_v1", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    from ..analysis.macro.cycles.kondratiev import compute_kuznets_extended
    _, rows = compute_kuznets_extended()
    text = json.dumps(rows, ensure_ascii=False)
    _ck.set(text)
    return text


@mcp.tool(
    name="cycle_nesting",
    description="四周期嵌套数据：基钦/朱格拉/库兹涅茨/康波合成Z值+相位序列（JSON数组），用于周期嵌套图与甘特图",
)
def cycle_nesting() -> str:
    """四周期百年+扩展数据对齐：composite_z 原始标准化值 + 离散相位 + 相位名称

    绘图优先使用 composite_z（FRED 扩展数据的原始 zscore，连续平滑），
    phase_name 用于甘特图颜色映射。
    保留 _cont / _signal 字段供参考，但不再作为主绘图数据源。
    """
    from ..shared.phase_utils import (
        get_phase_signal,
        zscore_to_phase_angle, phase_angle_to_signal,
        MACRO_PHASE_NAMES,
    )
    from ..analysis.macro.cycles.kondratiev import (
        compute_kitchin_extended,
        compute_juglar_extended,
        compute_kuznets_extended,
    )

    _ck_nest = CacheKey.init("cycles_nesting_v3", ttl=604800, ttl2=2592000)
    cached = _ck_nest.get()
    if cached is not None and isinstance(cached, str):
        return cached

    # ── 1. 拉取四周期扩展数据（FRED/世界银行，百年+年频） ──
    _, ki_rows = compute_kitchin_extended()
    _, ju_rows = compute_juglar_extended()
    _, ku_rows = compute_kuznets_extended()
    kondratiev_result, _ = _compute_kondratiev("pca")

    # ── 2. 构建康波逐行数据 ──
    k_years = kondratiev_result.get("years", [])
    k_zscore = kondratiev_result.get("zscore", [])

    # 保留相位角转换逻辑（参考备用），但主绘图使用原始 zscore
    k_zscore_vals = [z if z is not None else 0.0 for z in k_zscore] if k_zscore else []
    k_angles = zscore_to_phase_angle(k_zscore_vals)
    k_cont_signal = phase_angle_to_signal(k_angles)

    k_rows = []
    for i, year in enumerate(k_years):
        row = {"period": str(year)}
        if i < len(k_zscore):
            z = k_zscore[i]
            mom = k_zscore[i] - k_zscore[i - 1] if i > 0 else 0
            if abs(mom) < 0.005 and i > 0:
                mom = k_zscore[i - 1] - k_zscore[max(0, i - 5)]
            if mom > 0 and z < 0:
                phase = 1
            elif mom > 0 and z >= 0:
                phase = 2
            elif mom < 0 and z >= 0:
                phase = 3
            elif mom < 0 and z < 0:
                phase = 4
            else:
                phase = kondratiev_result.get("phase", 0)
            row["phase"] = phase
            row["phase_name"] = MACRO_PHASE_NAMES.get(phase, "未知")
        row["composite_z"] = round(k_zscore_vals[i], 4) if i < len(k_zscore_vals) else None
        row["cont_signal"] = round(k_cont_signal[i], 4) if i < len(k_cont_signal) else None
        k_rows.append(row)
    if k_rows:
        k_rows[-1]["phase"] = kondratiev_result.get("phase", 0)
        k_rows[-1]["phase_name"] = kondratiev_result.get("phase_name", "未知")

    # ── 3. 年频对齐：扩展数据已是年频，直接按 period 索引 ──
    def _annual_rows(rows):
        by_year: dict[str, dict] = {}
        for r in rows:
            p = str(r.get("period", ""))
            y = p[:4]
            if len(y) == 4:
                by_year[y] = r
        return by_year

    ki_ann = _annual_rows(ki_rows)
    ju_ann = _annual_rows(ju_rows)
    ku_ann = _annual_rows(ku_rows)
    ko_ann = _annual_rows(k_rows)

    # ── 4. 保留相位角转换（参考备用，不用于主绘图） ──
    # _RESERVED_PHASE_CONVERSION（存档，供后续对比验证）
    def _extract_zscore_series(ann_rows, key):
        years_sorted = sorted(ann_rows.keys())
        vals = []
        for y in years_sorted:
            v = ann_rows[y].get(key)
            vals.append(v if v is not None else 0.0)
        return years_sorted, vals

    ki_years_s, ki_zs = _extract_zscore_series(ki_ann, "composite_z")
    ki_angles = zscore_to_phase_angle(ki_zs)
    ki_cont = phase_angle_to_signal(ki_angles)
    ki_cont_map = {y: v for y, v in zip(ki_years_s, ki_cont)}

    ju_years_s, ju_zs = _extract_zscore_series(ju_ann, "composite_z")
    ju_angles = zscore_to_phase_angle(ju_zs)
    ju_cont = phase_angle_to_signal(ju_angles)
    ju_cont_map = {y: v for y, v in zip(ju_years_s, ju_cont)}

    ku_years_s, ku_zs = _extract_zscore_series(ku_ann, "composite_z")
    ku_angles = zscore_to_phase_angle(ku_zs)
    ku_cont = phase_angle_to_signal(ku_angles)
    ku_cont_map = {y: v for y, v in zip(ku_years_s, ku_cont)}

    ko_cont_map = {}
    for r in k_rows:
        y = str(r.get("period", ""))[:4]
        if len(y) == 4:
            ko_cont_map[y] = r.get("cont_signal", 0.0)

    # ── 5. 汇总年份并构建嵌套数据 ──
    all_years = sorted(set(list(ki_ann.keys()) + list(ju_ann.keys()) +
                           list(ku_ann.keys()) + list(ko_ann.keys())))
    nesting = []
    for y in all_years:
        entry: dict = {"period": y}
        for cid, ann in [
            ("kitchin", ki_ann),
            ("juglar", ju_ann),
            ("kuznets", ku_ann),
            ("kondratiev", ko_ann),
        ]:
            row = ann.get(y)
            if row:
                ph = row.get("phase", 0)
                entry[f"{cid}_phase"] = ph
                entry[f"{cid}_signal"] = get_phase_signal(ph)
                entry[f"{cid}_name"] = row.get("phase_name", "未知")
                # 核心绘图字段：原始标准化 zscore（连续平滑）
                entry[f"{cid}_z"] = row.get("composite_z")
            else:
                entry[f"{cid}_phase"] = 0
                entry[f"{cid}_signal"] = 0.0
                entry[f"{cid}_name"] = "—"
                entry[f"{cid}_z"] = None
        # 相位角转换信号（存档备用，与 composite_z 对比验证）
        entry["kitchin_cont"] = round(ki_cont_map.get(y, 0.0), 4)
        entry["juglar_cont"] = round(ju_cont_map.get(y, 0.0), 4)
        entry["kuznets_cont"] = round(ku_cont_map.get(y, 0.0), 4)
        entry["kondratiev_cont"] = round(ko_cont_map.get(y, 0.0), 4)
        nesting.append(entry)

    text = json.dumps(nesting, ensure_ascii=False)
    _ck_nest.set(text)
    return text


# ============================================================
#  周期数据缓存工具
# ============================================================

@mcp.tool(
    name="cycle_collect",
    description="预采集全部周期指标数据到本地 SQLite 缓存，避免每次分析重新拉取",
)
def cycle_collect() -> str:
    from ..shared.cycle_db import cache_all, stats
    results = cache_all()
    st = stats()
    lines = [f"=== 周期数据采集 ===  共 {len(st)} 个指标"]
    for name, cnt in sorted(st.items()):
        lines.append(f"  {name:25s} {cnt:>4} 条")
    for name, err in results.items():
        if isinstance(err, str) and err.startswith("❌"):
            lines.append(f"  {name:25s} {err}")

    # ── 高级缓存器：预热各周期分析计算结果 ──
    lines.append("")
    lines.append("=== 计算结果预热 ===")
    for cid, ckey in [("kitchin", "cycles_data_kitchin"),
                       ("juglar", "cycles_data_juglar"),
                       ("kuznets", "cycles_data_kuznets")]:
        try:
            _ck = CacheKey.init(ckey, ttl=604800, ttl2=2592000)
            if _ck.get() is None:
                _, _, res = _compute(cid, limit=0)
                _ck.set(json.dumps(res, ensure_ascii=False))
                lines.append(f"  {cid:10s} ✅ 计算并缓存 ({len(res)} 期)")
            else:
                lines.append(f"  {cid:10s} ✅ 已有缓存")
        except Exception as e:
            lines.append(f"  {cid:10s} ❌ {e}")

    try:
        _ck_k = CacheKey.init("cycles_report_kondratiev_pca_v3", ttl=604800, ttl2=2592000)
        if _ck_k.get() is None:
            # 走 kondratiev_cycle() 完整路径，它自己写缓存
            text = kondratiev_cycle("pca")
            lines.append(f"  kondratiev ✅ 已计算")
        else:
            lines.append(f"  kondratiev ✅ 已有缓存")
    except Exception as e:
        lines.append(f"  kondratiev ❌ {e}")

    return "\n".join(lines)


@mcp.tool(
    name="fred_data",
    description="FRED 数据查询。传注册名(fred_ppiaco)或任意 series_id(GDPC1/UNRATE/...)",
)
def fred_data(
    series: str = "fred_ppiaco",
    limit: int = 20,
) -> str:
    from ..data.sources.fred import SERIES, get as fred_get
    from ..data.sources.wb_fred_adapter import fetch_fred

    is_registered = series in SERIES
    series_id = SERIES[series][0] if is_registered else series.upper()
    raw = fred_get(series) if is_registered else fetch_fred(series_id)
    if not raw:
        return f"无数据: {series}"
    tag = "" if is_registered else " (未缓存)"
    out = [f"=== {series_id} === [{len(raw)} 条, {raw[0][0]} ~ {raw[-1][0]}]{tag}"]
    out.append("date,value")
    for d, v in raw[-limit:]:
        out.append(f"{d},{v:.2f}")
    return "\n".join(out)


@mcp.tool(
    name="fred_list",
    description="列出所有可采集的 FRED 数据集（共8个）",
)
def fred_list() -> str:
    from ..shared.cycle_db import list_fred
    items = list_fred()
    lines = [f"共 {len(items)} 个 FRED 指标"]
    for i in items:
        lines.append(f"  {i['key']:20s}  {i['series_id']:10s}  {i['desc']}")
    return "\n".join(lines)


@mcp.tool(
    name="wb_data",
    description="世界银行数据查询。传注册名(wb_gdp_growth)或任意 indicator+国家代码",
)
def wb_data(
    indicator: str = "wb_gdp_growth",
    country: str = "1W",
    limit: int = 20,
) -> str:
    from ..data.sources.world_bank import INDICATORS, get as wb_get
    from ..data.sources.wb_fred_adapter import fetch_wb

    is_registered = indicator in INDICATORS
    if is_registered:
        raw = wb_get(indicator)
        label = INDICATORS[indicator][0]
    else:
        raw = fetch_wb(indicator, country)
        label = indicator

    if not raw:
        return f"无数据: {indicator}"
    tag = "" if is_registered else " (未缓存)"
    out = [f"=== {label} === [{len(raw)} 条, {raw[0][0]} ~ {raw[-1][0]}]{tag}"]
    out.append("year,value")
    for y, v in raw[-limit:]:
        out.append(f"{y},{v:.2f}")
    return "\n".join(out)


@mcp.tool(
    name="wb_list",
    description="列出所有可采集的世界银行数据集（共7个）",
)
def wb_list() -> str:
    from ..shared.cycle_db import list_wb
    items = list_wb()
    lines = [f"共 {len(items)} 个世界银行指标"]
    for i in items:
        lines.append(f"  {i['key']:25s}  {i['indicator']:25s}  {i['desc']}")
    return "\n".join(lines)


@mcp.tool(
    name="cycle_cache_status",
    description="查看周期数据缓存状态",
)
def cycle_cache_status() -> str:
    from ..shared.cycle_db import stats
    st = stats()
    lines = [f"周期数据缓存: {len(st)} 个指标"]
    for name, cnt in sorted(st.items()):
        lines.append(f"  {name:25s} {cnt:>4} 条")
    if not st:
        lines.append("  (空，请先用 cycle_collect 采集)")
    return "\n".join(lines)


# ============================================================
#  康波周期（单独注册，参数更多）
# ============================================================
@mcp.tool(
    name="kondratiev_cycle",
    description="判断当前长波周期（康德拉季耶夫周期）阶段。可选方法: pca(默认, 8谱法+相位映射), wavelet(Morlet小波功率谱), bandpass(40-60年带通滤波)",
)
def kondratiev_cycle(
    method: str = Field("pca", description="计算方法: pca/wavelet/bandpass"),
) -> str:
    _ck = CacheKey.init(f"cycles_report_kondratiev_{method}_v3", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    result, vals = _compute_kondratiev(method)
    if not vals:
        return "数据不足（需要至少 20 年序列）"
    dp = result.get("dominant_period")
    ph = result.get("phase", 0)
    conf = result.get("confidence", 0)
    pv = result.get("pca_variance_ratio", 0)
    phase_names = ["未知", "回升期(复苏)", "繁荣期", "衰退期", "萧条期"]
    lines = [
        "═" * 50,
        "  康波周期(长波)定位",
        "═" * 50,
        f"  数据源: 世界银行 (65年长序列, 1960~2024)",
        f"  年份范围: {result.get('year_range', '?')}",
        f"  参与指标: {', '.join(result.get('indicators_used', []))}",
    ]
    pv_pct = f"{pv*100:.0f}%" if pv else "N/A"
    lines.append(f"  PCA第一主成分方差占比: {pv_pct}  {'⚠ 较低(<70%), 合成指数代表性有限' if pv and pv < 0.6 else '✅'}")
    if dp:
        lines.append(f"  主周期长度: {dp:.1f} 年  (置信度: {conf:.2f})")
        lines.append(f"  使用方法: {result.get('method_used', '?')}")

    # ── 全球线 ──
    g_ph = result.get("global_phase", 0)
    g_conf = result.get("global_confidence", 0)
    g_name = result.get("global_phase_name", phase_names[g_ph] if g_ph < len(phase_names) else "未知")
    lines.append("")
    lines.append("── 全球线 (FRED PPI+GS10 + 世行全球GDP) ──")
    lines.append(f"  当前相位: {g_ph} — {g_name}  置信度: {g_conf:.2f}")

    # ── 中国线 ──
    c_ph = result.get("china_phase", 0)
    c_conf = result.get("china_confidence", 0)
    c_name = result.get("china_phase_name", phase_names[c_ph] if c_ph < len(phase_names) else "未知")
    if c_ph > 0:
        lines.append("")
        lines.append("── 中国线 (中国GDP + 平减指数 + 城市化率) ──")
        lines.append(f"  当前相位: {c_ph} — {c_name}  置信度: {c_conf:.2f}")

    # ── 融合结果 ──
    lines.append("")
    lines.append("── 融合判定 ──")
    lines.append(f"  当前相位: {ph} — {result.get('phase_name', phase_names[ph])}  置信度: {conf:.2f}")
    if result.get("phase_confidence"):
        lines.append(f"  相位置信度: {result.get('phase_confidence', 0):.2f}")
    lines.append("")
    lines.append("── 康波历史参照 (5轮主流划分) ──")
    lines.append("  第1波 1782-1845 蒸汽/纺织 (谷1782 峰1815)")
    lines.append("  第2波 1845-1892 铁路/钢铁 (谷1845 峰1873)")
    lines.append("  第3波 1892-1948 电力/重工 (谷1892 峰1929)")
    lines.append("  第4波 1948-1991 汽车/石化 (谷1948 峰1973)")
    lines.append("  第5波 1991-至今  信息技术 (谷1991 峰2000)")
    lines.append(f"  → 当前数据覆盖: 第4波后半段~第5波 (1960~2024)")
    if ph == 2:
        lines.append("  机构对比: 中金/中信建投→复苏起点 | 海通/CMF→萧条延续 | 外资→不确定")
        lines.append("  → 本模型提示繁荣(高于均值的上升段), 与技术S曲线过渡期信号一致")
    elif ph == 3:
        lines.append("  机构对比: 中金/中信建投→复苏起点 | 海通/CMF→萧条延续 | 外资→不确定")
        lines.append("  → 本模型提示衰退(高于均值的下降段), 偏海通/CMF观点")
    elif ph == 1:
        lines.append("  机构对比: 中金/中信建投→复苏起点 | 海通/CMF→萧条延续 | 外资→不确定")
        lines.append("  → 本模型提示回升(低于均值的上升段), 偏中金/中信建投观点")
    elif ph == 4:
        lines.append("  机构对比: 中金/中信建投→复苏起点 | 海通/CMF→萧条延续 | 外资→不确定")
        lines.append("  → 本模型提示萧条(低于均值的下降段), 偏海通/CMF观点")
    lines.append("")
    lines.append(f"  数据精度: PCA方差占比={pv_pct}, 相位置信度={conf:.2f}, 方法={result.get('method_used', '?')}")
    slope = result.get("all_results", {}).get("slope", 0)
    if slope != 0:
        slope_dir = "上升" if slope > 0 else "下降"
        lines.append(f"  趋势斜率: {slope:.4f} ({slope_dir})")
    lines.append("═" * 50)
    text = "\n".join(lines)
    _ck.set(text)
    return text


@mcp.tool(
    name="chart_kondratiev_cycle",
    description="生成康波周期分析图（PCA合成指数+主周期标注），保存为PNG。可选方法: pca/wavelet/bandpass",
)
def chart_kondratiev_cycle(
    method: str = Field("pca", description="计算方法: pca/wavelet/bandpass"),
    output_path: str = Field("kondratiev_cycle.png", description="图表保存路径"),
) -> str:
    result, vals = _compute_kondratiev(method)
    if not vals:
        return "数据不足"
    return _gen_kondratiev_chart(result, vals, output_path)


@mcp.tool(
    name="data_kondratiev",
    description="获取康波周期原始数据（PCA合成指数序列）",
)
def data_kondratiev(
    method: str = Field("pca", description="计算方法: pca/wavelet/bandpass"),
) -> str:
    _ck = CacheKey.init(f"cycles_data_kondratiev_{method}_v5", ttl=604800, ttl2=2592000)
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached
    result, _ = _compute_kondratiev(method)

    # 将汇总 dict 转换为前端 CyclePage 期望的逐期数组格式
    # 前端要求 JSON.parse → Array，每行含 period + chartSeries key + 相位字段
    years = result.get("years", [])
    pca1 = result.get("pca1", [])
    zscore = result.get("zscore", [])
    cf_cycle = result.get("cf_cycle", [])
    global_zscore = result.get("global_zscore", [])
    china_zscore = result.get("china_zscore", [])
    global_cf_cycle = result.get("global_cf_cycle", [])
    china_cf_cycle = result.get("china_cf_cycle", [])
    # 逐行计算相位：基于 zscore 的 level+momentum 判定
    from ..shared.phase_utils import (
        get_phase_signal, MACRO_PHASE_NAMES,
        zscore_to_phase_angle, phase_angle_to_intensity, phase_angle_to_signal,
    )

    # 预计算连续相位角和强度 — 融合线
    zscore_vals = [z if z is not None else 0.0 for z in zscore] if zscore else []
    angles = zscore_to_phase_angle(zscore_vals)
    intensity = phase_angle_to_intensity(angles)
    cont_signal = phase_angle_to_signal(angles)

    # 全球线相位角
    g_zs_vals = [z if z is not None else 0.0 for z in global_zscore] if global_zscore else []
    g_angles = zscore_to_phase_angle(g_zs_vals)
    g_intensity = phase_angle_to_intensity(g_angles)

    # 中国线相位角
    c_zs_vals = [z if z is not None else 0.0 for z in china_zscore] if china_zscore else []
    c_angles = zscore_to_phase_angle(c_zs_vals)
    c_intensity = phase_angle_to_intensity(c_angles)

    rows = []
    for i, year in enumerate(years):
        row: dict = {"period": str(year)}
        if i < len(pca1):
            row["pca1"] = pca1[i]
        # ── 融合线 ──
        if i < len(zscore):
            row["zscore"] = zscore[i]
            z = zscore[i]
            mom = zscore[i] - zscore[i - 1] if i > 0 else 0
            if abs(mom) < 0.005 and i > 0:
                mom = zscore[i - 1] - zscore[max(0, i - 5)]
            if mom > 0 and z < 0:
                phase = 1
            elif mom > 0 and z >= 0:
                phase = 2
            elif mom < 0 and z >= 0:
                phase = 3
            elif mom < 0 and z < 0:
                phase = 4
            else:
                phase = result.get("phase", 0)
            row["phase"] = phase
            row["phase_name"] = MACRO_PHASE_NAMES.get(phase, "未知")
            row["cycle_signal"] = get_phase_signal(phase)
        if i < len(angles):
            row["phase_angle"] = round(angles[i], 4)
        if i < len(intensity):
            row["intensity"] = round(intensity[i], 4)
        if i < len(cont_signal):
            row["cont_signal"] = round(cont_signal[i], 4)
        if i < len(cf_cycle):
            row["cf_cycle"] = cf_cycle[i]
        # ── 全球线 ──
        if i < len(global_zscore):
            row["global_zscore"] = global_zscore[i]
        if i < len(g_intensity):
            row["global_intensity"] = round(g_intensity[i], 4)
        if i < len(global_cf_cycle):
            row["global_cf_cycle"] = global_cf_cycle[i]
        # ── 中国线 ──
        if i < len(china_zscore):
            row["china_zscore"] = china_zscore[i]
        if i < len(c_intensity):
            row["china_intensity"] = round(c_intensity[i], 4)
        if i < len(china_cf_cycle):
            row["china_cf_cycle"] = china_cf_cycle[i]
        rows.append(row)
    # 最后一行用 compute_kondratiev 的融合结果覆盖（最精确）
    if rows:
        rows[-1].update({
            "phase": result.get("phase", 0),
            "phase_name": result.get("phase_name", "未知"),
            "confidence": result.get("confidence", 0),
            "dominant_period": result.get("dominant_period"),
            "pca_variance_ratio": result.get("pca_variance_ratio", 0),
            "turning_probability": result.get("turning_probability", 0),
            "cycle_signal": get_phase_signal(result.get("phase", 0)),
            "global_phase": result.get("global_phase", 0),
            "global_phase_name": result.get("global_phase_name", "未知"),
            "global_confidence": result.get("global_confidence", 0),
            "china_phase": result.get("china_phase", 0),
            "china_phase_name": result.get("china_phase_name", "未知"),
            "china_confidence": result.get("china_confidence", 0),
        })

    text = json.dumps(rows, ensure_ascii=False)
    _ck.set(text)
    return text
