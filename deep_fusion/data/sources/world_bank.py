"""World Bank data source — DB-first, MCP-ready."""
from __future__ import annotations

from .wb_fred_adapter import fetch_wb as _fetch_wb
from ...shared.cycle_db import get as _db_get, set as _db_set

# 注册表: cache_key → (WB indicator, country, 描述)
INDICATORS: dict[str, tuple[str, str, str]] = {
    "wb_gdp_growth":     ("NY.GDP.MKTP.KD.ZG", "1W", "全球GDP增长率"),
    "wb_gdp_per_capita": ("NY.GDP.PCAP.KD",    "1W", "全球人均GDP"),
    "wb_trade_pct":      ("NE.TRD.GNFS.ZS",    "1W", "贸易占GDP比重"),
    "wb_population":     ("SP.POP.TOTL",       "1W", "总人口"),
    "wb_inflation":      ("FP.CPI.TOTL.ZG",    "1W", "CPI通胀率"),
    "wb_patent":         ("IP.PAT.RESD",       "1W", "居民专利申请量"),
    "wb_electricity":    ("EG.USE.ELEC.KH.PC", "1W", "人均用电量"),
}

COUNTRY_MAP = {"CN": "中国", "1W": "全球", "US": "美国", "JP": "日本", "DE": "德国"}


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
