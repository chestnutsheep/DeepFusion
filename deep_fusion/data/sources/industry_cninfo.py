"""巨潮资讯行业数据源：分类、市盈率。"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache


def get_pe_ratio() -> pd.DataFrame:
    """获取巨潮行业市盈率。

    Returns:
        DataFrame: [行业代码, 行业名称, 静态市盈率, 滚动市盈率, ...]
    """
    df = ak_cache(ak.stock_industry_pe_ratio_cninfo, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    # 巨潮列名不稳定，动态映射
    rename = {}
    for c in df.columns:
        if "行业" in c and ("名称" in c or "代码" in c):
            rename[c] = "industry_name" if "名称" in c else "industry_code"
        elif "市盈" in c or "PE" in c.upper():
            if "动" in c or "TTM" in c.upper():
                rename[c] = "pe_ttm"
            else:
                rename[c] = "pe_static"
        elif "市净" in c or "PB" in c.upper():
            rename[c] = "pb"
    df = df.rename(columns=rename)
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
