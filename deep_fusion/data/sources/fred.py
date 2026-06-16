"""FRED data source — DB-first, MCP-ready.

Each series registered in _FRED_INDICATORS can be:
  - collected into cycle_cache.db (batch)
  - queried individually (DB-first, live fallback)

FRED data is stored permanently in SQLite (cycle_cache.db) —
historical macro data doesn't change, so no expiry is needed.
"""
from __future__ import annotations

from .wb_fred_adapter import fetch_fred as _fetch_fred
from ...shared.cycle_db import get as _db_get, set as _db_set

# 注册表: cache_key → (FRED series_id, 描述)
SERIES: dict[str, tuple[str, str]] = {
    # ── 原始8个 ──
    "fred_ppiaco":   ("PPIACO",            "生产者价格指数(全商品), 1913~"),
    "fred_gs10":     ("GS10",              "10年期国债收益率, 1953~"),
    "fred_cpiaucns": ("CPIAUCNS",          "CPI 所有城镇消费者, 1913~"),
    "fred_gnpca":    ("GNPCA",             "实际 GNP, 1929~"),
    "fred_indpro":   ("INDPRO",            "工业生产指数, 1919~"),
    "fred_unrate":   ("UNRATE",            "失业率, 1948~"),
    "fred_fedfunds": ("FEDFUNDS",          "联邦基金利率, 1954~"),
    "fred_t5yiep":   ("T5YIE",             "5年期盈亏平衡通胀率, 2003~"),
    # ── 三周期扩展新增 ──
    "fred_mnfrir":    ("MNFRIR",           "制造商库存, 1919~"),
    "fred_whlslrir":  ("WHLSLRIR",         "批发商库存, 1919~"),
    "fred_mcumfn":    ("MCUMFN",           "制造业产能利用率, 1967~"),
    "fred_fpi":       ("FPI",              "私人固定投资, 1947~"),
    "fred_pnfi":      ("PNFI",             "非住宅固定投资, 1947~"),
    "fred_houst":     ("HOUST",            "新屋开工, 1959~"),
    "fred_ussthpi":   ("USSTHPI",          "美国房价指数, 1975~"),
    "fred_prfi":      ("PRFI",             "住宅固定投资, 1947~"),
    "fred_m2sl":      ("M2SL",             "M2货币存量, 1959~"),
    # ── 金融压力指标（国际监测核心新增） ──
    "fred_t10y2y":    ("T10Y2Y",           "10Y-2Y国债利差(日频), 倒挂=衰退信号, 1976~"),
    "fred_tedrate":   ("TEDRATE",          "TED利差(银行间信用压力), 1986~"),
    "fred_baa10ym":   ("BAA10YM",          "Baa企业债-10Y国债利差(信用风险), 1986~"),
    "fred_baa_aaa":   ("BAA_AAA",          "Baa-Aaa级企业债利差(违约风险分层), 1986~"),
    # ── 美国核心经济指标 ──
    "fred_payems":    ("PAYEMS",           "非农就业人数(千人), 1939~"),
    "fred_umcsent":   ("UMCSENT",          "密歇根消费者信心指数, 1978~"),
    "fred_rsafs":     ("RSAFS",            "零售销售(百万美元), 1992~"),
    "fred_cpilfesl":  ("CPILFESL",         "核心CPI(不含食品能源), 1957~"),
    "fred_gfdebtn":   ("GFDEBTN",          "美国联邦债务/GDP(%), 1939~"),
    # ── 亚太汇率压力 ──
    "fred_dexjpus":   ("DEXJPUS",          "日元/美元汇率(日频), 1978~"),
    "fred_dexkous":   ("DEXKOUS",          "韩元/美元汇率(月频), 1981~"),
    "fred_dexchus":   ("DEXCHUS",          "人民币/美元汇率(日频), 1981~"),
    # ── 亚太/欧洲经济指标 ──
    "fred_jpn_indpro":("JPNPROINDM1M",     "日本工业生产指数(月频), 1953~"),
    "fred_eu_unrate": ("LRHUTTTTEZM156S",  "欧元区失业率(月频), 2000~"),
}


def list_series() -> list[dict]:
    return [{"key": k, "series_id": v[0], "desc": v[1]} for k, v in SERIES.items()]


def get(cache_key: str) -> list[tuple[str, float]]:
    """DB-first 查询 FRED 序列。"""
    # 1. DB
    df = _db_get(cache_key)
    if df is not None:
        return list(zip(df["date"], df["value"]))

    # 2. 实时拉取
    if cache_key not in SERIES:
        raise ValueError(f"未知 FRED 序列: {cache_key}")
    series_id = SERIES[cache_key][0]
    raw = _fetch_fred(series_id)
    if not raw:
        return []

    # 3. 写回 DB
    dates = [r[0][:10] for r in raw]
    vals = [r[1] for r in raw]
    try:
        _db_set(cache_key, dates, vals)
    except Exception:
        pass
    return raw


def collect() -> dict[str, int]:
    """批量采集所有 FRED 序列。"""
    results = {}
    for cache_key, (series_id, desc) in SERIES.items():
        raw = _fetch_fred(series_id)
        if raw:
            dates = [r[0][:10] for r in raw]
            vals = [r[1] for r in raw]
            try:
                _db_set(cache_key, dates, vals)
                results[cache_key] = len(vals)
            except Exception as e:
                results[cache_key] = f"❌ {e}"
        else:
            results[cache_key] = "❌ 空"
    return results
