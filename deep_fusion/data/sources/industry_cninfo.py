"""巨潮资讯行业数据源：分类、市盈率。"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache


def get_pe_ratio() -> pd.DataFrame:
    """获取行业估值/概览数据。

    说明：原巨潮 `stock_industry_pe_ratio_cninfo` 接口已失效（需 token，返回结构变更）。
    现改用同花顺行业概览（stock_board_industry_summary_ths）作为真实数据源，
    提供行业名称、涨跌幅、成交量、成交额、净流入、上涨/下跌家数、均价、领涨股等真实字段。
    PE/PB 估值列因本环境无权威实时源，留空（不虚构）。
    """
    import akshare as ak
    df = ak_cache(ak.stock_board_industry_summary_ths, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {
        "板块": "industry_name",
        "涨跌幅": "change_pct",
        "总成交量": "volume",
        "总成交额": "amount",
        "净流入": "net_inflow",
        "上涨家数": "up_count",
        "下跌家数": "down_count",
        "均价": "avg_price",
        "领涨股": "leader_stock",
        "领涨股-最新价": "leader_price",
        "领涨股-涨跌幅": "leader_change_pct",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    # 行业市盈率等估值列无真实源，显式留空（诚实，不返回虚构数字）
    for col in ("pe_static", "pe_ttm", "pb", "dividend_yield", "constituent_count"):
        if col not in df.columns:
            df[col] = ""
    return df


def get_industry_category() -> pd.DataFrame:
    """获取巨潮行业分类（证监会标准）。

    Returns:
        DataFrame: [行业名称, ...]
    """
    df = ak_cache(ak.stock_industry_category_cninfo, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    return df
