import asyncio
from datetime import datetime, timedelta

import akshare as ak  # pyright: ignore[reportMissingImports]
from pydantic import Field

from ..cache import ak_cache_async
from ..server import mcp
from ..shared.utils import ak_cache


def _prev_quarter_end() -> str:
    today = datetime.now()
    q = (today.month - 1) // 3
    quarter_start_month = q * 3 + 1
    quarter_end = datetime(today.year if q > 0 or today.month > 3 else today.year - 1, quarter_start_month,
                           1) - timedelta(days=1)
    if quarter_end > today:
        quarter_end = datetime(today.year - 1, 10, 1) - timedelta(days=1)
    return quarter_end.strftime("%Y%m%d")


@mcp.tool(
    title="个股侧面消息",
    description="获取个股新闻、内部交易（高管持股变动）、股东人数变化、十大股东变动等内部人员行为印证数据",
)
def sentiment_side(
        symbol: str = Field(description="6位股票代码，如 002318"),
        market: str = Field("sh", description="市场: sh=沪, sz=深, bj=京"),
) -> str:
    results = {}

    news = ak_cache(ak.stock_news_em, symbol=symbol, ttl=3600)
    if news is not None and not news.empty:
        results["个股新闻"] = news.head(10).to_csv(index=False).strip()

    mgmt = ak_cache(ak.stock_management_change_ths, symbol=symbol, ttl=43200)
    if mgmt is not None and not mgmt.empty:
        results["高管持股变动"] = mgmt.head(10).to_csv(index=False, float_format="%.2f")

    gdhs = ak_cache(ak.stock_zh_a_gdhs_detail_em, symbol=symbol, ttl=43200)
    if gdhs is not None and not gdhs.empty:
        results["股东人数变化"] = gdhs.to_csv(index=False, float_format="%.2f")

    holders = ak_cache(ak.stock_gdfx_top_10_em, symbol=f"{market}{symbol}", date=_prev_quarter_end(), ttl=43200)
    if holders is not None and not holders.empty:
        results["十大股东变动"] = holders.head(10).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的侧面消息数据"


@mcp.tool(
    title="个股资金动向",
    description="获取个股资金流向、机构调研记录、机构持仓明细等外部机构反响与资金流向综合数据",
)
def capital_tracking(
        symbol: str = Field(description="6位股票代码，如 000425"),
        market: str = Field("sh", description="市场: sh=沪, sz=深, bj=京"),
) -> str:
    results = {}

    fund = ak_cache(ak.stock_individual_fund_flow, stock=symbol, market=market, ttl=3600)
    if fund is not None and not fund.empty:
        results["个股资金流"] = fund.tail(30).to_csv(index=False, float_format="%.2f")

    date_str = datetime.now().strftime("%Y%m%d")
    tj = ak_cache(ak.stock_jgdy_tj_em, date=date_str, ttl=43200)
    if tj is not None and not tj.empty:
        tj_symbol = tj[tj.iloc[:, 1] == symbol].head(5)
        if not tj_symbol.empty:
            results["机构调研统计"] = tj_symbol.to_csv(index=False, float_format="%.2f")
    detail = ak_cache(ak.stock_jgdy_detail_em, date=date_str, ttl=43200)
    if detail is not None and not detail.empty:
        detail_symbol = detail[detail.iloc[:, 1] == symbol].head(5)
        if not detail_symbol.empty:
            results["机构调研详细"] = detail_symbol.to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的资金动向数据"


@mcp.tool(
    title="财务指标分析",
    description="获取个股86项财务指标，包括营收、净利润、毛利率、净利率、ROE、每股收益等所有关键财务数据",
)
def financial_indicators(
        symbol: str = Field(description="6位股票代码，如 000001"),
        start_year: str = Field("2020", description="起始年份，如 2020"),
        limit: int = Field(20, description="返回期数"),
) -> str:
    results = {}
    info = ak_cache(ak.stock_profile_cninfo, symbol=symbol, ttl=43200)
    if info is not None and not info.empty:
        results["个股基本信息"] = info.to_string()
    indicators = ak_cache(ak.stock_financial_analysis_indicator, symbol=symbol, start_year=start_year, ttl=86400,
                          ttl2=172800)
    if indicators is not None and not indicators.empty:
        results["财务指标"] = indicators.tail(limit).to_csv(index=False, float_format="%.3f")
    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的财务指标数据"


@mcp.tool(
    title="三大财务报表",
    description="获取个股资产负债表、利润表、现金流量表等三大财务报表数据",
)
def financial_statements(
        symbol: str = Field(description="6位股票代码，如 600519"),
        market: str = Field("sh", description="市场标识: sh, sz, bj"),
) -> str:
    stock_code = f"{market}{symbol}"
    results = {}
    for stmt_name in ["资产负债表", "利润表", "现金流量表"]:
        df = ak_cache(ak.stock_financial_report_sina, stock=stock_code, symbol=stmt_name, ttl=86400, ttl2=172800)
        if df is not None and not df.empty:
            results[stmt_name] = df.to_csv(index=False, float_format="%.2f")
    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的财务报表数据"


@mcp.tool(
    title="同业比较",
    description="获取行业内成长性、估值、杜邦分析、公司规模等四个维度的同业对比数据",
)
async def peer_comparison(
        symbol: str = Field(description="6位股票代码，如 600519"),
        market: str = Field("sh", description="市场标识: sh, sz, bj"),
) -> str:
    stock_code = f"{market.upper()}{symbol}"
    # 4 个独立维度并发
    growth, valuation, dupont, scale = await asyncio.gather(
        ak_cache_async(ak.stock_zh_growth_comparison_em, symbol=stock_code, ttl=86400, ttl2=172800),
        ak_cache_async(ak.stock_zh_valuation_comparison_em, symbol=stock_code, ttl=86400, ttl2=172800),
        ak_cache_async(ak.stock_zh_dupont_comparison_em, symbol=stock_code, ttl=86400, ttl2=172800),
        ak_cache_async(ak.stock_zh_scale_comparison_em, symbol=stock_code, ttl=86400, ttl2=172800),
    )
    results = {}
    if growth is not None and not growth.empty:
        results["成长性比较"] = growth.to_csv(index=False, float_format="%.3f")
    if valuation is not None and not valuation.empty:
        results["估值比较"] = valuation.to_csv(index=False, float_format="%.3f")
    if dupont is not None and not dupont.empty:
        results["杜邦分析比较"] = dupont.to_csv(index=False, float_format="%.3f")
    if scale is not None and not scale.empty:
        results["公司规模比较"] = scale.to_csv(index=False, float_format="%.3f")
    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的同业比较数据"


@mcp.tool(
    title="港股关键指标",
    description="获取港股市场的股票财务报告关键指标",
)
def stock_indicators_hk(
        symbol: str = Field(description="5位港股代码，如 00700"),
):
    dfs = ak_cache(ak.stock_financial_hk_analysis_indicator_em, symbol=symbol, indicator="报告期")
    if dfs is None or dfs.empty:
        return f"未获取到财务指标: {symbol}"
    keys = dfs.to_csv(index=False, float_format="%.3f").strip().split("\n")
    return "\n".join(keys[0:15])


@mcp.tool(
    title="美股关键指标",
    description="获取美股市场的股票财务报告关键指标",
)
def stock_indicators_us(
        symbol: str = Field(description="美股字母代码，如 AAPL"),
):
    dfs = ak_cache(ak.stock_financial_us_analysis_indicator_em, symbol=symbol, indicator="单季报")
    if dfs is None or dfs.empty:
        return f"未获取到财务指标: {symbol}"
    keys = dfs.to_csv(index=False, float_format="%.3f").strip().split("\n")
    return "\n".join(keys[0:15])
