from __future__ import annotations
import json
import sys
import os
from pydantic import Field
from fastmcp import Context

from ..server import mcp

# ─── Python 3.13 兼容补丁 ───
import pkgutil
if not hasattr(pkgutil, 'ImpImporter'):
    pkgutil.ImpImporter = type('ImpImporter', (), {})

# 确保 core 目录在 import 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.data_clusters import anti_fraud_data, bl_pathology_data
from core.report_builder import build_report


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
    return json.dumps(report, ensure_ascii=False)
