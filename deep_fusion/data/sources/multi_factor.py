"""Multi-factor model data source.

Currently wraps article_ff_crr (Fama-French Current Research Returns).
FF3/FF5/SBMP/SOPP/SIP full time series data TBD.
"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache


def get_ff_summary() -> pd.DataFrame:
    """获取 Fama-French 多因子模型最新汇总数据（Current Research Returns）。

    Returns:
        DataFrame: [item, April 2026, Last 3 Months, Last 12 Months]
            包含 Size 组合回报数据
    """
    df = ak_cache(ak.article_ff_crr, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    return df
