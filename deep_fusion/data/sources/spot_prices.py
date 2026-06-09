"""Spot commodity prices from 99qh (99期货), as specified in 行业分析部分数据来源.md.

Key feature: single symbol returns ALL history from 2012 to present.
"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache

# 品种列表缓存
_symbol_cache: list[dict] | None = None


def list_symbols() -> list[dict]:
    """返回99qh所有可查品种。"""
    global _symbol_cache
    if _symbol_cache is not None:
        return _symbol_cache
    df = ak_cache(ak.spot_price_table_qh, ttl=86400)
    if df is None or df.empty:
        return []
    _symbol_cache = df.to_dict("records")
    return _symbol_cache


def get_spot(symbol: str) -> pd.DataFrame:
    """获取指定品种的现货历史走势（99qh）。

    Args:
        symbol: 品种名称，如 "螺纹钢"、"铜"、"铁矿石"、"原油"

    Returns:
        DataFrame: [日期, 期货收盘价, 现货价格]  从2012年至今
    """
    df = ak_cache(ak.spot_price_qh, symbol=symbol, ttl=3600)
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {"日期": "trade_date", "期货收盘价": "futures_close", "现货价格": "spot_price"}
    df = df.rename(columns=rename)
    return df.reset_index(drop=True)


def get_spots(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """批量获取多个品种。"""
    return {s: get_spot(s) for s in symbols}
