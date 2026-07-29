"""数据新鲜度管理模块 — 区分原始数据(Actual)和处理数据(Derived)。

设计原则:
  - 原始数据(Actual): PMI、CPI、GDP、行业K线等历史事实 → 永不过期，大胆入库
  - 处理/信号数据(Derived): 相位判定、zscore、技术指标、聚类 → 需新鲜度机制

新鲜度机制:
  1. 版本号锁定: Derived 缓存键含版本号，算法改了 +1 版本号即可自动失效旧缓存
  2. 增量追加: Actual DB-first 路径检查最新日期，若数据源有更新则追加新行（不删旧行）
  3. TTL 分级: Derived 数据按计算复杂度设不同 TTL
     - 轻量计算(相位标注/信号): TTL=3600 (1小时)
     - 中量计算(zscore/周期数据): TTL=604800 (7天) / ttl2=2592000 (30天)
     - 重量计算(DCC-GARCH/Granger): TTL=86400 (1天) / ttl2=604800 (7天)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Literal

logger = logging.getLogger(__name__)

DataKind = Literal["actual", "derived"]

# ── 数据分类注册表 ──────────────────────────────────────────
DATA_CLASSIFICATION: dict[str, dict] = {
    # ═══ 原始数据 (Actual) — 永不过期，增量追加 ═══

    # 1.1 宏观指标 (cycle_cache.db / data_lake.db)
    "cpi_yoy":               {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "ppi_yoy":               {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "pmi_macro":             {"kind": "actual", "freq": "月频", "source": "akshare", "db": "cycle_cache"},
    "gdp_quarterly":         {"kind": "actual", "freq": "季频", "source": "NBS",     "db": "cycle_cache"},
    "inventory_yoy":         {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "ind_yoy":               {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "fix_inv_monthly":       {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "re_dev_yoy":            {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "unemployment":          {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "equip_invest":          {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "manufacturing_invest":  {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "re_sales_area":         {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "re_new_start":          {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "capacity_util":         {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "house_price_yoy":       {"kind": "actual", "freq": "月频", "source": "NBS",     "db": "cycle_cache"},
    "m2_yearly":             {"kind": "actual", "freq": "月频", "source": "akshare", "db": "cycle_cache"},
    "CPI":                   {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "PPI":                   {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "PMI":                   {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "GDP":                   {"kind": "actual", "freq": "季频", "source": "akshare", "db": "data_lake"},
    "GDP_YEARLY":            {"kind": "actual", "freq": "年频", "source": "akshare", "db": "data_lake"},
    "INDUSTRIAL_VALUE_ADD":  {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "INVENTORY":             {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "FIXED_INVESTMENT":      {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "M2":                    {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "LPR":                   {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "UNEMPLOYMENT":          {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "SOCIAL_FINANCING":      {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "FX_RESERVES":           {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "EXPORT":                {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "IMPORT":                {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "TRADE_BALANCE":         {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "NON_MAN_PMI":           {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "CAIXIN_PMI":            {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "CAIXIN_SERVICES_PMI":   {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},
    "REAL_ESTATE_YOY":       {"kind": "actual", "freq": "月频", "source": "akshare", "db": "data_lake"},

    # 1.2 FRED/世界银行指标 (cycle_cache.db)
    "fred_ppiaco":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_gs10":             {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_cpiaucns":         {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_gnpca":            {"kind": "actual", "freq": "季频", "source": "FRED",    "db": "cycle_cache"},
    "fred_indpro":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_unrate":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_fedfunds":         {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_t5yiep":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_mnfrir":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_whlslrir":         {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_mcumfn":           {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_fpi":              {"kind": "actual", "freq": "季频", "source": "FRED",    "db": "cycle_cache"},
    "fred_pnfi":             {"kind": "actual", "freq": "季频", "source": "FRED",    "db": "cycle_cache"},
    "fred_houst":            {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "fred_ussthpi":          {"kind": "actual", "freq": "季频", "source": "FRED",    "db": "cycle_cache"},
    "fred_prfi":             {"kind": "actual", "freq": "季频", "source": "FRED",    "db": "cycle_cache"},
    "fred_m2sl":             {"kind": "actual", "freq": "月频", "source": "FRED",    "db": "cycle_cache"},
    "wb_gdp_growth":         {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_gdp_per_capita":     {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_trade_pct":          {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_population":         {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_inflation":          {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_patent":             {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},
    "wb_electricity":        {"kind": "actual", "freq": "年频", "source": "WB",      "db": "cycle_cache"},

    # 1.3 行业数据 (industry_data.db)
    "meso_industry_classify":  {"kind": "actual", "freq": "一次性", "source": "akshare", "db": "industry_data"},
    "meso_industry_daily":     {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "industry_data"},
    "meso_industry_valuation": {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "industry_data"},
    "meso_industry_fund_flow": {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "industry_data"},
    "meso_industry_financial": {"kind": "actual", "freq": "季频",   "source": "akshare", "db": "industry_data"},
    "meso_sw_classify":        {"kind": "actual", "freq": "一次性", "source": "akshare", "db": "industry_data"},
    "meso_spot_quotes":        {"kind": "actual", "freq": "实时",   "source": "akshare", "db": "industry_data"},

    # 1.4 个股/市场行情 (ak_cache 短TTL，不入永久库)
    "stock_zh_a_spot":         {"kind": "actual", "freq": "实时",   "source": "akshare", "db": "ak_cache"},
    "stock_zh_a_hist":         {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "stock_individual_info":   {"kind": "actual", "freq": "一次性", "source": "akshare", "db": "ak_cache"},
    "stock_financial":         {"kind": "actual", "freq": "季频",   "source": "akshare", "db": "ak_cache"},
    "stock_fund_flow":         {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "stock_sentiment":         {"kind": "actual", "freq": "实时",   "source": "akshare", "db": "ak_cache"},
    "bond_yields":             {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "fx_rates":                {"kind": "actual", "freq": "实时",   "source": "akshare", "db": "ak_cache"},
    "futures_prices":          {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "fund_nav":                {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "pm_spot_prices":          {"kind": "actual", "freq": "实时",   "source": "akshare", "db": "ak_cache"},
    "crypto_prices":           {"kind": "actual", "freq": "实时",   "source": "OKX",     "db": "none"},
    "industry_sw_daily":       {"kind": "actual", "freq": "日频",   "source": "akshare", "db": "ak_cache"},
    "industry_sw_tree":        {"kind": "actual", "freq": "一次性", "source": "akshare", "db": "ak_cache"},
    "industry_sw_constituents":{"kind": "actual", "freq": "一次性", "source": "akshare", "db": "ak_cache"},

    # 1.5 公共行情 SQL (market_data.db) — 个股/指数日K 的唯一持久层
    #     所有上层任务(Claw 定时任务/前端/工具)只读此库；写入仅由
    #     deep_fusion/data/sources/market_collector.py 完成（详见 docs/data_contract.md）。
    "market_stock_daily":    {"kind": "actual", "freq": "日频",   "source": "sina",   "db": "market_data"},
    "market_index_daily":    {"kind": "actual", "freq": "日频",   "source": "sina",   "db": "market_data"},
    "market_stock_info":     {"kind": "actual", "freq": "一次性", "source": "akshare", "db": "market_data"},

    # ═══ 处理/信号数据 (Derived) — 版本号锁定 + TTL 分级 ═══

    # 2.1 周期相位/信号 (CacheKey L1+L2)
    "cycles_data_kitchin":             {"kind": "derived", "version": "v2",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_juglar":              {"kind": "derived", "version": "v2",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_kuznets":             {"kind": "derived", "version": "v2",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_kitchin_extended_v1": {"kind": "derived", "version": "v1",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_juglar_extended_v1":  {"kind": "derived", "version": "v1",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_kuznets_extended_v1": {"kind": "derived", "version": "v1",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_nesting_v4":               {"kind": "derived", "version": "v4",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_report_kondratiev_pca_v3": {"kind": "derived", "version": "v3",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_report_kondratiev_wavelet_v3": {"kind": "derived", "version": "v3", "weight": "中量", "ttl": 604800, "ttl2": 2592000},
    "cycles_report_kondratiev_bandpass_v3": {"kind": "derived", "version": "v3", "weight": "中量", "ttl": 604800, "ttl2": 2592000},
    "cycles_data_kondratiev_pca_v5":   {"kind": "derived", "version": "v5",  "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_kondratiev_wavelet_v5": {"kind": "derived", "version": "v5", "weight": "中量", "ttl": 604800,  "ttl2": 2592000},
    "cycles_data_kondratiev_bandpass_v5": {"kind": "derived", "version": "v5", "weight": "中量", "ttl": 604800,  "ttl2": 2592000},

    # 2.2 技术指标 (ak_cache)
    "stock_tech_indicators":           {"kind": "derived", "version": "",    "weight": "轻量", "ttl": 3600,   "ttl2": 86400},

    # 2.3 行业分析信号 (实时计算，不缓存)
    "industry_themes":                 {"kind": "derived", "version": "",    "weight": "中量", "ttl": 0,      "ttl2": 0},
    "industry_themes_dcc":             {"kind": "derived", "version": "",    "weight": "重量", "ttl": 0,      "ttl2": 0},
    "industry_themes_causality":       {"kind": "derived", "version": "",    "weight": "重量", "ttl": 0,      "ttl2": 0},
}

# ── Actual 数据的增量更新检查间隔 ──────────────────────────
ACTUAL_UPDATE_INTERVAL: dict[str, timedelta] = {
    "实时":   timedelta(minutes=5),
    "日频":   timedelta(hours=4),
    "月频":   timedelta(days=3),
    "季频":   timedelta(days=15),
    "年频":   timedelta(days=60),
    "一次性": timedelta(days=365),
}

# ── Derived 数据的 TTL 分级 ─────────────────────────────────
DERIVED_TTL_TIERS: dict[str, tuple[int, int]] = {
    "轻量": (3600, 86400),
    "中量": (604800, 2592000),
    "重量": (86400, 604800),
}


def classify(key: str) -> DataKind:
    """查询数据分类。"""
    entry = DATA_CLASSIFICATION.get(key)
    if entry:
        return entry["kind"]
    logger.warning("freshness: 未注册的数据键 '%s', 默认为 actual", key)
    return "actual"


def get_entry(key: str) -> dict | None:
    """获取数据分类详情。"""
    return DATA_CLASSIFICATION.get(key)


def needs_incremental_update(key: str, db_latest_date: str | None) -> bool:
    """判断 Actual 数据是否需要增量更新。

    DB-first 路径调用此函数：DB有数据但可能不是最新时，尝试增量追加。
    原始数据永不过期，但需要检查是否有新数据可追加。
    """
    entry = DATA_CLASSIFICATION.get(key)
    if not entry or entry["kind"] != "actual":
        return False

    if db_latest_date is None:
        return True  # DB 无数据，必须拉取

    freq = entry.get("freq", "月频")
    interval = ACTUAL_UPDATE_INTERVAL.get(freq, timedelta(days=3))

    try:
        latest = _parse_date(db_latest_date)
        if latest is None:
            return True
        age = datetime.now() - latest
        return age > interval
    except Exception:
        return True


def _parse_date(date_str: str) -> datetime | None:
    """解析各种日期格式：YYYY-MM-DD, YYYY-MM, YYYY-QN, YYYY"""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y%m%d", "%Y%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    if "Q" in date_str.upper():
        parts = date_str.upper().replace("Q", " ").split()
        if len(parts) == 2:
            try:
                year, quarter = int(parts[0]), int(parts[1])
                return datetime(year, quarter * 3, 1)
            except (ValueError, IndexError):
                pass
    return None


def derived_cache_key(base_key: str, version: str | None = None) -> str:
    """为 Derived 数据构建带版本号的缓存键。

    注册表中有版本号的直接使用，否则用传入的 version。
    """
    entry = DATA_CLASSIFICATION.get(base_key)
    if entry and entry.get("version"):
        return base_key  # 注册表中已含版本号
    if version:
        return f"{base_key}_{version}"
    logger.warning("freshness: Derived 数据 '%s' 未注册版本号", base_key)
    return base_key


def get_actual_update_interval(key: str) -> timedelta:
    """获取 Actual 数据的增量更新检查间隔。"""
    entry = DATA_CLASSIFICATION.get(key)
    if not entry:
        return timedelta(days=3)
    freq = entry.get("freq", "月频")
    return ACTUAL_UPDATE_INTERVAL.get(freq, timedelta(days=3))


def get_derived_ttl(key: str) -> tuple[int, int]:
    """获取 Derived 数据的 TTL 配置。"""
    entry = DATA_CLASSIFICATION.get(key)
    if not entry:
        return (604800, 2592000)
    weight = entry.get("weight", "中量")
    return DERIVED_TTL_TIERS.get(weight, (604800, 2592000))
