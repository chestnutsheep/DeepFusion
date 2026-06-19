"""同花顺行业数据源：分类、指数行情、资金流、行业一览。"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache


def get_industry_list() -> pd.DataFrame:
    """获取同花顺行业分类列表。

    Returns:
        DataFrame: [name, code]  90 行
    """
    df = ak_cache(ak.stock_board_industry_name_ths, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"name": "industry_name", "code": "industry_code"})
    return df


def get_industry_index(symbol: str, start: str = "20000101", end: str = "") -> pd.DataFrame:
    """获取同花顺行业指数历史行情（OHLCV）。

    Args:
        symbol: 行业名称/代码，如 "银行"、"881155"
        start: 起始日期 YYYYMMDD
        end: 截止日期 YYYYMMDD，默认今天

    Returns:
        DataFrame: [日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额]
    """
    df = ak_cache(
        ak.stock_board_industry_index_ths,
        symbol=symbol,
        start_date=start,
        end_date=end or "20261231",
        ttl=3600,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    # 标准化列名
    rename = {
        "日期": "trade_date",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "收盘价": "close",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = df.rename(columns=rename)
    df["industry_code"] = symbol
    return df


def get_industry_summary() -> pd.DataFrame:
    """获取同花顺行业一览（实时行情+资金流概览）。

    Returns:
        DataFrame: [序号, 板块, 涨跌幅, 总成交量, 总成交额, 净流入, ...]
    """
    df = ak_cache(ak.stock_board_industry_summary_ths, ttl=300)
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {"板块": "industry_name", "涨跌幅": "change_pct", "净流入": "net_inflow"}
    df = df.rename(columns=rename)
    return df


def get_fund_flow() -> pd.DataFrame:
    """获取同花顺行业资金流。

    Returns:
        DataFrame: [行业, 行业指数, 行业-涨跌幅, 流入资金, 流出资金, 净额, ...]
    """
    df = ak_cache(ak.stock_fund_flow_industry, ttl=300)
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {
        "行业": "industry_name",
        "行业指数": "industry_index",
        "行业-涨跌幅": "change_pct",
        "流入资金": "inflow",
        "流出资金": "outflow",
        "净额": "net_amount",
        "公司家数": "company_count",
        "领涨股": "leader_stock",
        "领涨股-涨跌幅": "leader_pct_change",
        "当前价": "current_price",
    }
    df = df.rename(columns=rename)
    return df
