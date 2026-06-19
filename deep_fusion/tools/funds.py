"""基金数据工具模块"""

from datetime import datetime

import akshare as ak
from pydantic import Field

from ..server import mcp
from ..shared.schema import format_error_csv
from ..shared.utils import ak_cache


@mcp.tool(
    title="获取基金基本信息",
    description="获取基金的基本信息，包括基金名称、类型、规模、管理人等详细信息",
)
def fund_info(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
):
    # 雪球（第一顺位）—— 返回基金基本信息
    try:
        df = ak_cache(ak.fund_individual_basic_info_xq, symbol=code)
        if df is not None and not df.empty:
            lines = [f"{row['item']}: {row['value']}" for _, row in df.iterrows()]
            return "\n".join(lines)
    except Exception:
        pass
    # 东方财富ETF（第二顺位）
    try:
        df = ak_cache(ak.fund_etf_fund_info_em, symbol=code)
        if df is not None and not df.empty:
            return df.to_csv(index=False, float_format="%.4f")
    except Exception:
        pass
    # 东方财富普通（回退）
    df = ak_cache(ak.fund_open_fund_info_em, symbol=code)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.4f")


@mcp.tool(
    title="获取基金净值历史",
    description="获取基金的历史净值数据，包括单位净值、累计净值、日增长率等，用于分析基金业绩表现",
)
def fund_nav(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
        limit: int = Field(30, description="返回数量(int)，建议30-252", strict=False),
):
    df = ak_cache(ak.fund_open_fund_daily_em)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    df = df.loc[df.iloc[:, 0] == code].tail(limit).copy() if len(df) > 0 else df.tail(limit).copy()
    return df.to_csv(index=False, float_format="%.4f")


@mcp.tool(
    title="获取基金持仓明细",
    description="获取基金的股票持仓明细，包括持仓股票代码、名称、持仓比例等，用于分析基金投资组合",
)
def fund_holdings(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
):
    df = ak_cache(ak.fund_portfolio_hold_em, symbol=code, date=str(datetime.now().year), ttl=43200)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取基金排行榜",
    description="获取不同类型基金的排行榜数据，包括收益率、规模等指标，支持按时间周期和基金类型筛选",
)
def fund_ranking(
        fund_type: str = Field(
            "全部",
            description="基金类型，支持: 全部, 股票型, 混合型, 债券型, 指数型, QDII, ETF, LOF",
        ),
):
    df = ak_cache(ak.fund_open_fund_rank_em, symbol=fund_type)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=fund_type)
    df = df.head(100).copy()
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取基金债券持仓",
    description="天天基金网-基金档案-债券持仓：返回基金持有的债券代码、名称、占净值比例、持仓市值等（缓存12h，季度更新）",
)
def fund_bond_holdings(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
        date: str = Field("", description="年份YYYY，留空自动取当前年"),
):
    if not date:
        from datetime import datetime
        date = str(datetime.now().year)
    try:
        df = ak_cache(ak.fund_portfolio_bond_hold_em, symbol=code, date=date, ttl=43200)
        if df is not None and not df.empty:
            return df.to_csv(index=False, float_format="%.2f")
    except Exception:
        pass
    return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)


@mcp.tool(
    title="获取基金行业配置",
    description="天天基金网-基金档案-行业配置：返回基金在各行业的持仓比例、市值等（缓存12h，季度更新）",
)
def fund_industry_allocation(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
        date: str = Field("", description="年份YYYY，留空自动取当前年"),
):
    if not date:
        from datetime import datetime
        date = str(datetime.now().year)
    try:
        df = ak_cache(ak.fund_portfolio_industry_allocation_em, symbol=code, date=date, ttl=43200)
        if df is not None and not df.empty:
            return df.to_csv(index=False, float_format="%.2f")
    except Exception:
        pass
    return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)


@mcp.tool(
    title="获取基金风险收益分析",
    description="雪球基金-基金详情-数据分析：返回基金近1/3/5年的年化波动率、夏普比率、最大回撤、较同类风险收益比等指标（缓存24h）",
)
def fund_analysis(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
):
    df = ak_cache(ak.fund_individual_analysis_xq, symbol=code, ttl=86400)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取基金盈利概率",
    description="雪球基金-基金详情-盈利概率：历史任意时点买入，持有满X时间的盈利概率和平均收益（缓存24h）",
)
def fund_profit_probability(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
):
    df = ak_cache(ak.fund_individual_profit_probability_xq, symbol=code, ttl=86400)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取基金资产配置",
    description="雪球基金-基金详情-持仓资产比例：返回股票/现金/债券/其他的大类资产仓位占比（缓存72h，季度更新）",
)
def fund_asset_allocation(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
        date: str = Field("", description="季度日期YYYYMMDD，留空自动取最新季度"),
):
    if not date:
        from datetime import datetime
        y, m = datetime.now().year, datetime.now().month
        if m <= 3:
            q = f"{y - 1}1231"
        elif m <= 6:
            q = f"{y}0331"
        elif m <= 9:
            q = f"{y}0630"
        else:
            q = f"{y}0930"
        date = q
    df = ak_cache(ak.fund_individual_detail_hold_xq, symbol=code, date=date, ttl=259200)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.2f")
