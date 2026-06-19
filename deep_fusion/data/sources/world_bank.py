"""World Bank data source — DB-first, MCP-ready."""
from __future__ import annotations

from .wb_fred_adapter import fetch_wb as _fetch_wb
from ...shared.cycle_db import get as _db_get, set as _db_set

# 注册表: cache_key → (WB indicator, country, 描述)
INDICATORS: dict[str, tuple[str, str, str]] = {
    "wb_gdp_growth": ("NY.GDP.MKTP.KD.ZG", "1W", "全球GDP增长率"),
    "wb_gdp_per_capita": ("NY.GDP.PCAP.KD", "1W", "全球人均GDP"),
    "wb_trade_pct": ("NE.TRD.GNFS.ZS", "1W", "贸易占GDP比重"),
    "wb_population": ("SP.POP.TOTL", "1W", "总人口"),
    "wb_inflation": ("FP.CPI.TOTL.ZG", "1W", "CPI通胀率"),
    "wb_patent": ("IP.PAT.RESD", "1W", "居民专利申请量"),
    "wb_electricity": ("EG.USE.ELEC.KH.PC", "1W", "人均用电量"),
    # ── 国际金融压力监测新增（按国家分查） ──
    "wb_debt_gdp_cn": ("GC.DOD.TOTL.GD.ZS", "CN", "中国政府债务/GDP(%)"),
    "wb_debt_gdp_us": ("GC.DOD.TOTL.GD.ZS", "US", "美国政府债务/GDP(%)"),
    "wb_debt_gdp_jp": ("GC.DOD.TOTL.GD.ZS", "JP", "日本政府债务/GDP(%)"),
    "wb_debt_gdp_kr": ("GC.DOD.TOTL.GD.ZS", "KR", "韩国政府债务/GDP(%)"),
    "wb_reserves_cn": ("FI.RES.TOTL.MO", "CN", "中国外汇储备(月进口覆盖)"),
    "wb_reserves_kr": ("FI.RES.TOTL.MO", "KR", "韩国外汇储备(月进口覆盖)"),
    "wb_reserves_jp": ("FI.RES.TOTL.MO", "JP", "日本外汇储备(月进口覆盖)"),
    "wb_gdp_growth_cn": ("NY.GDP.MKTP.KD.ZG", "CN", "中国GDP增长率(%)"),
    "wb_gdp_growth_us": ("NY.GDP.MKTP.KD.ZG", "US", "美国GDP增长率(%)"),
    "wb_gdp_growth_jp": ("NY.GDP.MKTP.KD.ZG", "JP", "日本GDP增长率(%)"),
    "wb_gdp_growth_kr": ("NY.GDP.MKTP.KD.ZG", "KR", "韩国GDP增长率(%)"),
    "wb_inflation_cn": ("FP.CPI.TOTL.ZG", "CN", "中国CPI通胀率(%)"),
    "wb_inflation_us": ("FP.CPI.TOTL.ZG", "US", "美国CPI通胀率(%)"),
    "wb_inflation_jp": ("FP.CPI.TOTL.ZG", "JP", "日本CPI通胀率(%)"),
    "wb_inflation_kr": ("FP.CPI.TOTL.ZG", "KR", "韩国CPI通胀率(%)"),
    "wb_trade_cn": ("NE.TRD.GNFS.ZS", "CN", "中国贸易占GDP比重(%)"),
    "wb_trade_jp": ("NE.TRD.GNFS.ZS", "JP", "日本贸易占GDP比重(%)"),
    "wb_trade_kr": ("NE.TRD.GNFS.ZS", "KR", "韩国贸易占GDP比重(%)"),
}

COUNTRY_MAP = {"CN": "中国", "1W": "全球", "US": "美国", "JP": "日本", "KR": "韩国", "DE": "德国", "EUU": "欧元区"}


def list_indicators() -> list[dict]:
    return [{"key": k, "indicator": v[0], "country_code": v[1], "desc": v[2]} for k, v in INDICATORS.items()]


def get(cache_key: str, country: str | None = None) -> list[tuple[int, float]]:
    """DB-first 查询 World Bank 序列。

    Args:
        cache_key: wb_gdp_growth / wb_population 等
        country: 可选覆盖国家代码（默认使用注册表中的）
    """
    # 1. DB（使用固定的 cache_key，不管 country 参数）
    if country:
        alt_key = f"{cache_key}_{country}"
    else:
        alt_key = cache_key

    df = _db_get(alt_key)
    if df is not None:
        return [(int(r[0]), r[1]) for r in zip(df["date"], df["value"])]

    df = _db_get(cache_key)
    if df is not None:
        return [(int(r[0]), r[1]) for r in zip(df["date"], df["value"])]

    # 2. 实时拉取
    if cache_key not in INDICATORS:
        raise ValueError(f"未知 WB 指标: {cache_key}")
    indicator, default_country, _ = INDICATORS[cache_key]
    code = country or default_country
    raw = _fetch_wb(indicator, code)
    if not raw:
        return []

    # 3. 写回
    dates = [str(r[0]) for r in raw]
    vals = [r[1] for r in raw]
    try:
        _db_set(alt_key if country else cache_key, dates, vals)
    except Exception:
        pass
    return raw


def collect() -> dict[str, int]:
    results = {}
    for cache_key, (indicator, country, desc) in INDICATORS.items():
        raw = _fetch_wb(indicator, country)
        if raw:
            dates = [str(r[0]) for r in raw]
            vals = [r[1] for r in raw]
            try:
                _db_set(cache_key, dates, vals)
                results[cache_key] = len(vals)
            except Exception as e:
                results[cache_key] = f"❌ {e}"
        else:
            results[cache_key] = "❌ 空"
    return results
