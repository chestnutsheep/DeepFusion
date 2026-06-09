import json

import akshare as ak
from fastmcp import Context
from pydantic import Field

from ..server import mcp
from ..shared.fields import field_market
from ..shared.utils import ak_cache, ak_search_async

# 代码→名称列映射：不同数据源返回的列名不同
_CODE_COLS = ["code", "证券代码", "A股代码", "symbol", "基金代码", "代码"]
_NAME_COLS = ["name", "证券简称", "A股简称", "cname", "基金名称", "名称", "中文名称"]


def _extract_code_name(info) -> dict:
    """从 pandas Series 中提取代码和名称，兼容不同列名"""
    result = {"code": "", "name": "", "market": ""}
    if info is None:
        return result
    for col in _CODE_COLS:
        if col in info.index and info[col] is not None:
            result["code"] = str(info[col])
            break
    for col in _NAME_COLS:
        if col in info.index and info[col] is not None:
            result["name"] = str(info[col])
            break
    return result


@mcp.tool(
    title="查找股票代码",
    description="根据股票名称、公司名称等关键词查找股票代码。当你已知股票代码时，建议直接使用其他工具（如 market_prices）跳过搜索",
)
async def search(
    keyword: str = Field(description="搜索关键词，公司名称、股票名称、股票代码、证券简称"),
    market: str = field_market,
    ctx: Context | None = None,
):
    if ctx:
        await ctx.report_progress(0, 100, "正在初始化搜索...")
    if ctx:
        await ctx.report_progress(30, 100, "正在查询市场数据...")
    info = await ak_search_async(None, keyword, market)
    if ctx:
        await ctx.report_progress(70, 100, "正在匹配关键词...")
    if info is not None:
        if ctx:
            await ctx.report_progress(100, 100, "搜索完成")
        result = _extract_code_name(info)
        result["market"] = market
        return json.dumps(result, ensure_ascii=False)
    if ctx:
        await ctx.report_progress(100, 100, "未找到结果")
    return json.dumps({"code": "", "name": "", "market": market, "error": f"Not Found for {keyword}"}, ensure_ascii=False)


@mcp.tool(
    title="市场概况总览",
    description="获取各板块实时行情：沪深京A股、创业板、科创板、ST股票、新股等。不传板块参数则返回全部A股行情",
)
def market_overview(
    板块: str = Field("全部A股", description="板块: 全部A股, 沪A, 深A, 京A, 创业板, 科创板, ST, 新股"),
    limit: int = Field(30, description="返回行数"),
) -> str:
    df = _fetch_spot(板块)
    if df is None or df.empty:
        return ""
    return df.head(limit).to_csv(index=False, float_format="%.2f")


def _fetch_spot(market: str = "全部A股") -> "pd.DataFrame | None":
    """市场行情查询：优先新浪 → 东方财富回退。
    
    新浪 stock_zh_a_spot() 无参数返回全市场，本地按代码前缀过滤板块。
    东方财富各板块有独立接口，作为降级回退。
    """
    # 本地过滤规则（新浪代码前缀）
    prefix_map = {
        "沪A": ("sh", lambda c: c.startswith("sh")),
        "深A": ("sz", lambda c: c.startswith("sz")),
        "京A": ("bj", lambda c: c.startswith("bj")),
        "创业板": ("sz30", lambda c: c[:4] == "sz30" if len(c) >= 4 else False),
        "科创板": ("sh68", lambda c: c[:4] == "sh68" if len(c) >= 4 else False),
    }

    # 新浪（优先）
    try:
        df = ak_cache(ak.stock_zh_a_spot, ttl=300, ttl2=600)
        if df is not None and not df.empty:
            if market == "全部A股" or market == "ST" or market == "新股":
                return df
            prefix, fil = prefix_map.get(market, ("", lambda c: True))
            if prefix:
                filtered = df[df['代码'].apply(fil)]
                if len(filtered) > 0:
                    return filtered
            return df
    except Exception:
        pass

    # 东方财富回退（各板块独立接口）
    fallback_map = {
        "全部A股": ak.stock_zh_a_spot_em,
        "沪A": ak.stock_sh_a_spot_em,
        "深A": ak.stock_sz_a_spot_em,
        "京A": ak.stock_bj_a_spot_em,
        "创业板": ak.stock_cy_a_spot_em,
        "科创板": ak.stock_kc_a_spot_em,
        "ST": ak.stock_zh_a_st_em,
        "新股": ak.stock_new_a_spot_em,
    }
    func = fallback_map.get(market, ak.stock_zh_a_spot_em)
    df = ak_cache(func, ttl=300, ttl2=600)
    return df if df is not None and not df.empty else None


@mcp.tool(
    title="个股档案信息",
    description="获取个股基本信息（东方财富+雪球）、股本股东、十大股东、高管变动、历史分红等综合档案数据",
)
def individual_info(
    symbol: str = Field(description="6位股票代码，如 600519"),
    market: str = Field("sh", description="市场: sh=沪, sz=深, bj=京"),
) -> str:
    results = {}

    info = ak_cache(ak.stock_individual_info_em, symbol=symbol, ttl=43200)
    if info is not None and not info.empty:
        results["基本信息(东方财富)"] = info.to_string()

    xq = ak_cache(ak.stock_individual_basic_info_xq, symbol=f"{market.upper()}{symbol}", ttl=43200)
    if xq is not None and not xq.empty:
        results["基本信息(雪球)"] = xq.to_string()

    holder = ak_cache(ak.stock_main_stock_holder, stock=symbol, ttl=43200)
    if holder is not None and not holder.empty:
        results["主要股东"] = holder.head(10).to_csv(index=False, float_format="%.2f")

    mgmt = ak_cache(ak.stock_management_change_ths, symbol=symbol, ttl=43200)
    if mgmt is not None and not mgmt.empty:
        results["高管变动"] = mgmt.head(10).to_csv(index=False, float_format="%.2f")

    dividend = ak_cache(ak.stock_dividend_cninfo, symbol=symbol, ttl=43200)
    if dividend is not None and not dividend.empty:
        results["历史分红"] = dividend.head(10).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未找到 {symbol} 的数据"


@mcp.tool(
    title="个股历史行情",
    description="获取个股日/周/月K线、分钟线、分笔数据、盘前数据等综合历史行情",
)
def individual_hist(
    symbol: str = Field(description="6位股票代码，如 000001"),
    period: str = Field("daily", description="周期: daily=日线, weekly=周线, monthly=月线"),
    limit: int = Field(30, description="返回天数"),
    minute_period: str = Field("5", description="分钟级别: 1, 5, 15, 30, 60"),
) -> str:
    results = {}

    # 腾讯源（稳定）→ 东方财富回退
    market = "sh" if symbol.startswith("6") else "sz"
    kline = None
    try:
        kline = ak_cache(ak.stock_zh_a_daily, symbol=f"{market}{symbol}", adjust="qfq", ttl=3600)
    except Exception:
        pass
    if kline is None or kline.empty:
        kline = ak_cache(
            ak.stock_zh_a_hist, symbol=symbol, period=period,
            start_date="19700101", end_date="22220101",
            ttl=3600,
        )
    if kline is not None and not kline.empty:
        results["K线数据"] = kline.tail(limit).to_csv(index=False, float_format="%.2f")

    min_data = ak_cache(
        ak.stock_zh_a_hist_min_em, symbol=symbol, period=minute_period,
        ttl=3600,
    )
    if min_data is not None and not min_data.empty:
        results[f"{minute_period}分钟线"] = min_data.tail(limit).to_csv(index=False, float_format="%.2f")

    tick = ak_cache(ak.stock_intraday_em, symbol=symbol, ttl=300)
    if tick is not None and not tick.empty:
        results["分笔数据"] = tick.tail(limit).to_csv(index=False, float_format="%.2f")

    pre_open = ak_cache(ak.stock_zh_a_hist_pre_min_em, symbol=symbol, ttl=300)
    if pre_open is not None and not pre_open.empty:
        results["盘前数据"] = pre_open.tail(limit).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else f"未获取到 {symbol} 的历史行情"


@mcp.tool(
    title="获取市场历史价格",
    description="统一获取股票/ETF历史价格及技术指标，输出标准化行情字段。支持A股/H股/美股及ETF",
)
def market_prices(
    symbol: str = Field(description="股票代码，如 000001（A股）、00700（港股）、AAPL（美股）"),
    market: str = field_market,
    period: str = Field("daily", description="周期: daily(日线)、weekly(周线，不支持美股)"),
    limit: int = Field(30, description="返回数量"),
    asset: str = Field("equity", description="资产类型: equity/etf"),
) -> str:
    from datetime import datetime, timedelta

    import pandas as pd

    from ..shared.indicators import add_technical_indicators
    from ..shared.normalize import normalize_price_df

    if period == "weekly":
        delta = {"weeks": limit + 62}
    else:
        delta = {"days": limit + 62}
    start_date = (datetime.now() - timedelta(**delta)).strftime("%Y%m%d")

    def stock_us_daily(symbol, start_date="2025-01-01", period="daily"):
        dfs = ak.stock_us_daily(symbol=symbol)
        if dfs is None or dfs.empty:
            return None
        dfs.rename(columns={"date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量"}, inplace=True)
        dfs["换手率"] = None
        dfs.index = pd.to_datetime(dfs["日期"], errors="coerce")
        return dfs[start_date:"2222-01-01"]

    def fund_etf_hist_sina(symbol, market="sh", start_date="2025-01-01", period="daily"):
        dfs = ak.fund_etf_hist_sina(symbol=f"{market}{symbol}")
        if dfs is None or dfs.empty:
            return None
        dfs.rename(columns={"date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量"}, inplace=True)
        dfs["换手率"] = None
        dfs.index = pd.to_datetime(dfs["日期"], errors="coerce")
        return dfs[start_date:"2222-01-01"]

    markets = [
        ["sh", ak.stock_zh_a_hist, {}, "equity"],
        ["sz", ak.stock_zh_a_hist, {}, "equity"],
        ["hk", ak.stock_hk_hist, {}, "equity"],
        ["us", stock_us_daily, {}, "equity"],
        ["sh", fund_etf_hist_sina, {"market": "sh"}, "etf"],
        ["sz", fund_etf_hist_sina, {"market": "sz"}, "etf"],
    ]
    for m in markets:
        if m[0] != market:
            continue
        if m[3] != asset:
            continue
        extra = m[2] if isinstance(m[2], dict) else {}
        kws = {"period": period, "start_date": start_date, **extra}
        dfs = ak_cache(m[1], symbol=symbol, ttl=3600, **kws)
        if dfs is None or dfs.empty:
            continue
        add_technical_indicators(dfs, dfs["收盘"], dfs["最低"], dfs["最高"])
        currency_map = {"sh": "CNY", "sz": "CNY", "hk": "HKD", "us": "USD"}
        currency = currency_map.get(market, "CNY")
        return normalize_price_df(dfs, {"date": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘",
                                        "volume": "成交量", "amount": "成交额"}, source="akshare", currency=currency,
                                  limit=limit, float_format="%.2f", date_unit=str, indicator_map={
                "macd": "MACD", "dif": "DIF", "dea": "DEA",
                "kdj_k": "KDJ.K", "kdj_d": "KDJ.D", "kdj_j": "KDJ.J",
                "rsi": "RSI",
                "boll_u": "BOLL.U", "boll_m": "BOLL.M", "boll_l": "BOLL.L",
            })
    return normalize_price_df(None, {}, source="akshare", currency="", limit=limit, date_unit=str)
