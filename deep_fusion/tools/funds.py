"""基金数据工具模块"""

import io
import os
import re
import requests
from datetime import datetime

import akshare as ak
import pandas as pd
from pydantic import Field

from ..server import mcp
from ..shared.schema import format_error_csv
from ..shared.utils import ak_cache


def _em_proxies():
    px = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    return {"http": px, "https": px} if px else None


def _eastmoney_fund_holdings(code: str, hold_type: str = "jjcc") -> pd.DataFrame:
    """直接抓取东方财富基金 F10 持仓(html 表格)，避免 fund_portfolio_hold_em / fund_portfolio_bond_hold_em 接口失效。

    这是真实数据源（天天基金网披露的基金季报持仓），非虚构兜底。
    hold_type: "jjcc" 股票持仓, "zqcc" 债券持仓
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
               "Referer": "https://fundf10.eastmoney.com/"}
    proxies = _em_proxies()
    for month in (12, 9, 6, 3):  # 从最新季度往前找，优先返回有数据的季度
        year = datetime.now().year if month <= ((datetime.now().month - 1) // 3 * 3 + 3) else datetime.now().year - 1
        try:
            r = requests.get(
                "https://fundf10.eastmoney.com/FundArchivesDatas.aspx",
                params={"type": hold_type, "code": code, "year": str(year), "month": str(month)},
                headers=headers, proxies=proxies, timeout=20, verify=False,
            )
        except Exception:
            continue
        if not r.ok:
            continue
        m = re.search(r'content:\"(.*?)\"', r.text, re.S)
        if not m:
            continue
        html = m.group(1).replace('\\"', '"').replace("\\/", "/").replace("\\r", "").replace("\\n", "")
        try:
            tables = pd.read_html(io.StringIO(html))
        except Exception:
            continue
        if not tables:
            continue
        df = tables[0]
        if df is None or len(df) == 0:  # 该季度尚未披露 -> 试更早季度
            continue
        df.columns = [str(c).split("(")[0].strip() for c in df.columns]
        return df
    return pd.DataFrame()


def _eastmoney_fund_nav(code: str, limit: int = 30) -> pd.DataFrame:
    """直接抓取东方财富基金历史净值 API（api.fund.eastmoney.com/f10/lsjz），真实可靠。

    返回列：日期(FSRQ) / 单位净值(DWJZ) / 累计净值(LJJZ) / 日增长率(JZZZL) 等。
    """
    import os
    import requests

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://fundf10.eastmoney.com/"}
    proxies = _em_proxies()
    try:
        r = requests.get(
            "https://api.fund.eastmoney.com/f10/lsjz",
            params={"fundCode": code, "pageIndex": 1, "pageSize": max(limit, 1),
                    "startDate": "", "endDate": "", "_": 1},
            headers=headers, proxies=proxies, timeout=15, verify=False,
        )
        j = r.json()
        lst = (j.get("Data") or {}).get("LSJZList") or []
        if not lst:
            return pd.DataFrame()
        df = pd.DataFrame(lst)
        df = df.rename(columns={"FSRQ": "日期", "DWJZ": "单位净值", "LJJZ": "累计净值",
                                "JZZZL": "日增长率(%)", "SGZT": "申购状态", "SHZT": "赎回状态"})
        keep = [c for c in ["日期", "单位净值", "累计净值", "日增长率(%)", "申购状态", "赎回状态"] if c in df.columns]
        return df[keep].head(limit).copy()
    except Exception:
        return pd.DataFrame()


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
    # 东方财富净值/ETF 历史（第二顺位，直连 lsjz API 真实源）
    df = _eastmoney_fund_nav(code, limit=30)
    if df is not None and not df.empty:
        return df.to_csv(index=False, float_format="%.4f")
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
    df = _eastmoney_fund_nav(code, limit=limit)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.4f")


@mcp.tool(
    title="获取基金持仓明细",
    description="获取基金的股票持仓明细，包括持仓股票代码、名称、持仓比例等，用于分析基金投资组合",
)
def fund_holdings(
        code: str = Field(description="基金代码，例如: 000001(华夏成长)"),
):
    # 优先直连东财 F10 真实持仓（避免 fund_portfolio_hold_em 解析层损坏）
    df = _eastmoney_fund_holdings(code, hold_type="jjcc")
    if df is None or len(df) == 0:
        # 回退到 akshare（若其解析层修复）
        try:
            df = ak_cache(ak.fund_portfolio_hold_em, symbol=code, date=str(datetime.now().year), ttl=43200)
        except Exception:
            df = None
    if df is None or len(df) == 0:
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
    # 优先直连东财 F10 债券持仓（真实源，避免 fund_portfolio_bond_hold_em 解析层损坏）
    df = _eastmoney_fund_holdings(code, hold_type="zqcc")
    if df is None or len(df) == 0:
        try:
            df = ak_cache(ak.fund_portfolio_bond_hold_em, symbol=code, date=date, ttl=43200)
        except Exception:
            df = None
    if df is None or len(df) == 0:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=code)
    return df.to_csv(index=False, float_format="%.2f")


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
