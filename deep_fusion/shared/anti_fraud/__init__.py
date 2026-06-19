"""反诈个股深度分析子包。

提供：
  - akshare_api: 股票代码智能解析 + 暴雷分析六大模块数据获取
  - data_clusters: 5 个数据簇管线（反诈/暴雷/板块热度/周期轮动等）
  - report_builder: 反诈报告 JSON 构建器（7 块 REPORT schema）
"""

from .akshare_api import StockCode, resolve_stock_code
from .data_clusters import (
    anti_fraud_data,
    bl_pathology_data,
    tech_invest_data,
    sector_hotness_data,
    cycle_rotation_data,
)
from .report_builder import build_report, build_sector_report

__all__ = [
    "StockCode",
    "resolve_stock_code",
    "anti_fraud_data",
    "bl_pathology_data",
    "tech_invest_data",
    "sector_hotness_data",
    "cycle_rotation_data",
    "build_report",
    "build_sector_report",
]
