"""Cycle dispatch: CYCLES configs + _compute + report/chart helpers"""
import logging

from .common import _classify_kitchin, _classify_juglar, _classify_kuznets
from .engine import CycleEngine, CycleConfig, IndicatorDef

logger = logging.getLogger(__name__)

# ── _nbs — lazy-resolved fetch wrapper ──

def _nbs(name: str, key: str) -> IndicatorDef:
    """DB-first NBS data fetcher.

    Cache key convention: strip "fetch_" prefix from fn name.
    e.g. fetch_ind_yoy → cache key "ind_yoy"
    """
    _cache_key = name.replace("fetch_", "").replace("_nbs_", "")
    def _resolve():
        from ....shared.cycle_db import get, set as db_set
        from ....tools.cycles import _FN_MAP
        cached = get(_cache_key)
        if cached is not None:
            return cached["date"].tolist(), [float(v) if v is not None else None for v in cached["value"]]
        dates, vals = _FN_MAP[name]()
        if dates:
            try:
                db_set(_cache_key, dates, vals)
            except Exception:
                pass
        return dates, vals
    return IndicatorDef(key=key, fetch_fn=_resolve)


# ── 4 份配置表 ──────────────────────────────────────────

CYCLES: dict[str, CycleConfig] = {
    "kitchin": CycleConfig(
        id="kitchin", name="基钦周期(库存周期)", desc="库存-需求交叉法判断基钦周期4阶段",
        indicators=[
            _nbs("fetch_ind_yoy", "demand_yoy"),
            _nbs("fetch_inventory_yoy", "inventory_yoy"),
            _nbs("fetch_fix_inv_monthly", "fix_inv_yoy"),
            _nbs("fetch_pmi", "pmi"),
            _nbs("fetch_m2_yoy", "m2_yoy"),
        ],
        core_key="inventory_yoy", requires=["demand_yoy"], ma_window=3,
        classify_fn=_classify_kitchin,
        phase_names={1: "主动去库存", 2: "被动去库存", 3: "主动补库存", 4: "被动补库存"},
    ),
    "juglar": CycleConfig(
        id="juglar", name="朱格拉周期(固定资本投资周期)",
        desc="设备投资(0.4)+制造业固投(0.25)+固投总量(0.15)+产能利用率(0.2)加权 → 4阶段",
        indicators=[
            _nbs("fetch_equip_invest", "equip_yoy"),              # 核心 0.4
            _nbs("fetch_manufacturing_invest", "manufacturing_yoy"),  # 辅助 0.25
            _nbs("fetch_fix_inv_monthly", "fix_inv_yoy"),         # 辅助 0.15
            _nbs("fetch_capacity_util", "capacity_util"),         # 辅助 0.2
            _nbs("fetch_ind_yoy", "ind_yoy"),
            IndicatorDef(key="ppi_yoy", akshare_fn="macro_china_ppi", akshare_col="当月同比增长"),
            _nbs("fetch_pmi", "pmi"),
        ],
        core_key="fix_inv_yoy", requires=["manufacturing_yoy", "fix_inv_yoy"], ma_window=6,
        classify_fn=_classify_juglar,
        phase_names={1: "复苏", 2: "繁荣", 3: "衰退", 4: "萧条"},
    ),
    "kuznets": CycleConfig(
        id="kuznets", name="库兹涅茨周期(房地产周期)",
        desc="房价(0.5)+[销售(0.2)+新开工(0.2)+开发投资(0.1)]加权 CF 带通 → 4阶段",
        indicators=[
            _nbs("fetch_house_price", "house_price_yoy"),         # 主判定 0.5
            _nbs("fetch_re_sales_area", "sales_yoy"),             # 辅助 0.2
            _nbs("fetch_re_new_start", "new_start_yoy"),          # 辅助 0.2
            _nbs("fetch_re_dev_yoy", "re_yoy"),                   # 辅助 0.1
            _nbs("fetch_pmi", "pmi"),
        ],
        core_key="house_price_yoy", requires=["sales_yoy", "re_yoy"], ma_window=6,
        classify_fn=_classify_kuznets,
        phase_names={1: "复苏", 2: "繁荣", 3: "衰退", 4: "萧条"},
    ),
}

CYCLE_METADATA = {
    "kitchin": {
        "name": "kitchin_cycle",
        "desc": "判断当前库存周期（基钦周期）阶段",
        "chart_name": "chart_kitchin_cycle",
    },
    "juglar": {
        "name": "juglar_cycle",
        "desc": "判断当前固定资本投资周期（朱格拉周期）阶段",
        "chart_name": "chart_juglar_cycle",
    },
    "kuznets": {
        "name": "kuznets_cycle",
        "desc": "判断当前房地产周期（库兹涅茨周期）阶段",
        "chart_name": "chart_kuznets_cycle",
    },
}


# ── Compute pipeline ──────────────────────────────────

def _compute(cycle_id: str, limit: int = 60):
    cfg = CYCLES[cycle_id]
    engine = CycleEngine(cfg)
    return engine.run(limit)


def _fmt_report(periods, data, results, phase_key: str, dir_key: str, val_key: str, name: str) -> str:
    if not results:
        return f"{name}: 数据不足"
    last = results[-1]
    phase = last.get(phase_key, 0)
    dir_val = last.get(dir_key, 0)
    val = last.get(val_key)
    lines = [
        f"=== {name} ===",
        f"  最新周期: {last.get('period', '?')}",
        f"  阶段: {phase} ({last.get(phase_key + '_name', '未知')})",
        f"  {dir_key}: {dir_val:+d}",
        f"  {val_key}: {val}",
        "",
    ]
    return "\n".join(lines)


def _make_report_fn(cid, pk, dk, vk, nm):
    def _fn(limit: int = 0) -> str:
        p, d, r = _compute(cid, limit)
        return _fmt_report(p, d, r, pk, dk, vk, nm)
    _fn.__name__ = f"{cid}_cycle"
    return _fn


def _make_chart_fn(cid):
    def _fn(output_path: str = f"{cid}_cycle.png", limit: int = 0) -> str:
        p, d, r = _compute(cid, limit)
        if not r:
            return "数据不足"
        from .kondratiev import _chart_dispatch
        return _chart_dispatch(cid, r, d, output_path)
    _fn.__name__ = f"chart_{cid}_cycle"
    return _fn


def _chart_dispatch(cid: str, results, data, path: str):
    if cid == "kitchin":
        from .kondratiev import _gen_kitchin_chart
        return _gen_kitchin_chart(results, data, path)
    elif cid == "juglar":
        from .kondratiev import _gen_juglar_chart
        return _gen_juglar_chart(results, data, path)
    elif cid == "kuznets":
        from .kondratiev import _gen_kuznets_chart
        return _gen_kuznets_chart(results, data, path)
    return "未知周期"
