from __future__ import annotations
import json
from datetime import date, datetime

from pydantic import Field
from fastmcp import Context

from ..server import mcp
from ..shared.anti_fraud import anti_fraud_data, bl_pathology_data, build_report


def _json_default(o):
    """处理 akshare 返回的 date/Timestamp/NaN 等不可序列化对象。"""
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    # pandas Timestamp / NaT
    try:
        import pandas as pd
        if isinstance(o, pd.Timestamp):
            return o.isoformat() if not pd.isna(o) else None
    except ImportError:
        pass
    # numpy 类型
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            val = float(o)
            import math
            return None if math.isnan(val) else val
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
    except ImportError:
        pass
    # float NaN
    if isinstance(o, float):
        import math
        return None if math.isnan(o) else o
    return str(o)


@mcp.tool(
    title="反诈个股深度分析",
    description="对指定股票执行反诈深度分析，返回完整的7块REPORT JSON（meta/overview/anomaly/barrier/crossCheck/verdict/sentiment）",
)
async def anti_fraud_report(
    symbol: str = Field(description="股票代码，如 002598"),
    concept: str = Field(default="", description="概念名称，如 钠电池"),
    ctx: Context | None = None,
) -> str:
    """反诈个股深度分析，返回REPORT JSON"""
    af_data = anti_fraud_data(symbol=symbol, concept=concept)
    bl_data = bl_pathology_data(symbol=symbol)
    report = build_report(symbol=symbol, concept=concept,
                         anti_fraud_data=af_data, bl_pathology_data=bl_data)
    return json.dumps(report, ensure_ascii=False, default=_json_default)
