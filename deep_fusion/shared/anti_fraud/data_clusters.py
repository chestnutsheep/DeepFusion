"""
数据分析簇管线 —— 一类数据簇一个调用，一次吐出该分析场景需要的所有数据。

共 5 个数据簇：
  1. tech_invest_data       新兴技术投研
  2. anti_fraud_data        反诈验证
  3. bl_pathology_data      暴雷病理学
  4. sector_hotness_data    板块热度
  5. cycle_rotation_data    周期定位+行业轮动（部分功能待实现）

设计原则：
  - 输入参数统一，内部自动映射到各 akshare 接口的不同参数格式
  - 复用 isolated-tools 的 StockCode 智能解析器
  - 单个底层调用失败不阻塞整体，对应 key 返回 {"error": "原因"}
  - 个股类调用遍历 symbols 列表，结果以 symbol 为 key
  - 走 DeepFusion 规矩：akshare 调用统一用 ak_cache 缓存，
    季度末/交易日用 shared.utils 现成实现
"""

from datetime import datetime, timedelta

import akshare as ak  # pyright: ignore[reportMissingImports]
import pandas as pd
from pandas import Series

from .akshare_api import (
    resolve_stock_code, StockCode,
    BALANCE_SHEET_FIELDS, PROFIT_SHEET_FIELDS, CASH_FLOW_FIELDS,
)
from ..utils import _prev_quarter_end, recent_trade_date
from ...cache import ak_cache


# ──────────────────────────────────────────────
# 内部工具函数
# ──────────────────────────────────────────────

def _df_to_records(df) -> list:
    """DataFrame 转 list[dict]，None 返回空列表"""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    return df.to_dict("records")


def _recent_trade_date_str() -> str:
    """最近交易日 YYYYMMDD（shared.utils.recent_trade_date 返回 date 对象）"""
    d = recent_trade_date()
    return d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d)


# ──────────────────────────────────────────────
# 底层数据获取函数
# ──────────────────────────────────────────────

def _individual_info(sc: StockCode) -> dict:
    """个股档案信息"""
    result = {}
    info = ak_cache(ak.stock_individual_info_em, symbol=sc.symbol_pure, ttl=43200)
    if info is not None and not info.empty:
        result["基本信息"] = _df_to_records(info) if hasattr(info, "to_dict") else str(info)
    holder = ak_cache(ak.stock_main_stock_holder, stock=sc.symbol_pure, ttl=43200)
    if holder is not None and not holder.empty:
        if "截至日期" in holder.columns and len(holder) > 0:
            latest_date = holder["截至日期"].dropna().iloc[0]
            holder = holder[holder["截至日期"] == latest_date]
        result["主要股东"] = _df_to_records(holder.head(10))
    mgmt = ak_cache(ak.stock_management_change_ths, symbol=sc.symbol_pure, ttl=43200)
    if mgmt is not None and not mgmt.empty:
        result["高管变动"] = _df_to_records(mgmt.head(10))
    dividend = ak_cache(ak.stock_dividend_cninfo, symbol=sc.symbol_pure, ttl=43200)
    if dividend is not None and not dividend.empty:
        result["历史分红"] = _df_to_records(dividend.head(10))
    return result


def _financial_indicators(sc: StockCode, start_year: str = "2020", limit: int = 20) -> dict:
    """86项财务指标"""
    result = {}
    info = ak_cache(ak.stock_individual_info_em, symbol=sc.symbol_pure, ttl=43200)
    if info is not None and not info.empty:
        result["个股基本信息"] = _df_to_records(info) if hasattr(info, "to_dict") else str(info)
    indicators = ak_cache(
        ak.stock_financial_analysis_indicator,
        symbol=sc.symbol_pure, start_year=start_year, ttl=86400, ttl2=172800,
    )
    if indicators is not None and not indicators.empty:
        result["财务指标"] = _df_to_records(indicators.tail(limit))
    return result


def _financial_statements(sc: StockCode, limit: int = 20) -> dict:
    """三大财务报表
    统一用东方财富接口，字段更全，与暴雷簇数据源一致。
    """
    result = {}
    em_calls = [
        ("资产负债表", ak.stock_balance_sheet_by_report_em, BALANCE_SHEET_FIELDS),
        ("利润表", ak.stock_profit_sheet_by_report_em, PROFIT_SHEET_FIELDS),
        ("现金流量表", ak.stock_cash_flow_sheet_by_report_em, CASH_FLOW_FIELDS),
    ]
    for stmt_name, fn, field_map in em_calls:
        df = ak_cache(fn, symbol=sc.symbol_em, ttl=86400, ttl2=172800)
        if df is not None and not df.empty:
            available = [c for c in field_map if c in df.columns]
            if available:
                sub = df[available].copy()
                sub.columns = [field_map[c] for c in available]
                # 资产负债表额外算存贷比
                if stmt_name == "资产负债表" and "货币资金" in sub.columns and "总负债" in sub.columns:
                    sub["存贷比"] = sub["货币资金"] / sub["总负债"]
                result[stmt_name] = _df_to_records(sub.head(limit))
            else:
                result[stmt_name] = _df_to_records(df.head(limit))
    return result


def _market_prices(sc: StockCode, limit: int = 60) -> list:
    """历史行情"""
    delta_days = limit + 62
    start_date = (datetime.now() - timedelta(days=delta_days)).strftime("%Y%m%d")
    df = ak_cache(ak.stock_zh_a_daily, symbol=sc.symbol_em, adjust="qfq", ttl=3600)
    if df is None or (hasattr(df, "empty") and df.empty):
        df = ak_cache(
            ak.stock_zh_a_hist, symbol=sc.symbol_pure, period="daily",
            start_date=start_date, end_date="22220101", ttl=3600,
        )
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    col_map = {"日期": "date", "开盘": "open", "收盘": "close",
               "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    return _df_to_records(df.tail(limit))


def _capital_tracking(sc: StockCode) -> dict:
    """资金动向"""
    result = {}
    fund = ak_cache(ak.stock_individual_fund_flow, stock=sc.symbol_pure, market=sc.prefix_em, ttl=3600)
    if fund is not None and not fund.empty:
        result["个股资金流"] = _df_to_records(fund.tail(30))
    date_str = datetime.now().strftime("%Y%m%d")
    tj = ak_cache(ak.stock_jgdy_tj_em, date=date_str, ttl=43200)
    if tj is not None and not tj.empty:
        tj_symbol = tj[tj.iloc[:, 1] == sc.symbol_pure].head(5)
        if not tj_symbol.empty:
            result["机构调研统计"] = _df_to_records(tj_symbol)
    detail = ak_cache(ak.stock_jgdy_detail_em, date=date_str, ttl=43200)
    if detail is not None and not detail.empty:
        detail_symbol = detail[detail.iloc[:, 1] == sc.symbol_pure].head(5)
        if not detail_symbol.empty:
            result["机构调研详细"] = _df_to_records(detail_symbol)
    return result


def _peer_comparison(sc: StockCode) -> dict:
    """同业比较"""
    result = {}
    stock_code = sc.symbol_xq
    for key, fn in [
        ("成长性比较", ak.stock_zh_growth_comparison_em),
        ("估值比较", ak.stock_zh_valuation_comparison_em),
        ("杜邦分析比较", ak.stock_zh_dupont_comparison_em),
        ("公司规模比较", ak.stock_zh_scale_comparison_em),
    ]:
        df = ak_cache(fn, symbol=stock_code, ttl=86400, ttl2=172800)
        if df is not None and not df.empty:
            result[key] = _df_to_records(df)
    return result


def _sentiment_side(sc: StockCode) -> dict:
    """个股侧面消息"""
    result = {}
    news = ak_cache(ak.stock_news_em, symbol=sc.symbol_pure, ttl=3600)
    if news is not None and not news.empty:
        result["个股新闻"] = _df_to_records(news.head(10))
    mgmt = ak_cache(ak.stock_management_change_ths, symbol=sc.symbol_pure, ttl=43200)
    if mgmt is not None and not mgmt.empty:
        result["高管持股变动"] = _df_to_records(mgmt.head(10))
    gdhs = ak_cache(ak.stock_zh_a_gdhs_detail_em, symbol=sc.symbol_pure, ttl=43200)
    if gdhs is not None and not gdhs.empty:
        result["股东人数变化"] = _df_to_records(gdhs)
    holders = ak_cache(ak.stock_gdfx_top_10_em, symbol=sc.symbol_em, date=_prev_quarter_end(), ttl=43200)
    if holders is not None and not holders.empty:
        result["十大股东变动"] = _df_to_records(holders.head(10))
    return result


def _stock_tech_indicators(sc: StockCode) -> dict:
    """技术指标"""
    df = ak_cache(ak.stock_zh_a_daily, symbol=sc.symbol_em, adjust="qfq", ttl=3600)
    if df is None or (hasattr(df, "empty") and df.empty):
        df = ak_cache(ak.stock_zh_a_hist, symbol=sc.symbol_pure, period="daily",
                      start_date="20240101", end_date="22220101", ttl=3600)
    if df is None or (hasattr(df, "empty") and df.empty):
        return {"error": f"无法获取 {sc.symbol_pure} 的K线数据"}

    col_map = {"日期": "date", "开盘": "open", "收盘": "close",
               "最高": "high", "最低": "low", "成交量": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if "close" not in df.columns:
        return {"error": "无收盘价数据"}

    result = {"symbol": sc.symbol_pure}
    latest = df.tail(1).iloc[0]
    result["date"] = str(latest.get("date", ""))
    result["close"] = float(latest["close"])

    for n in [5, 10, 20, 60]:
        if len(df) >= n:
            result[f"MA{n}"] = round(float(df["close"].tail(n).mean()), 4)

    if len(df) >= 35:
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_val: Series = (dif - dea) * 2
        result["MACD"] = round(float(macd_val.iloc[-1]), 4)
        result["DIF"] = round(float(dif.iloc[-1]), 4)
        result["DEA"] = round(float(dea.iloc[-1]), 4)

    if len(df) >= 15 and "high" in df.columns and "low" in df.columns:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        result["RSI"] = round(float(rsi.iloc[-1]), 4)

        low_min = df["low"].rolling(9).min()
        high_max = df["high"].rolling(9).max()
        rsv = (df["close"] - low_min) / (high_max - low_min).replace(0, 1e-10) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        result["KDJ_K"] = round(float(k.iloc[-1]), 4)
        result["KDJ_D"] = round(float(d.iloc[-1]), 4)
        result["KDJ_J"] = round(float(j.iloc[-1]), 4)

    if len(df) >= 20:
        ma20 = df["close"].rolling(20).mean()
        std20 = df["close"].rolling(20).std()
        result["BOLL_U"] = round(float((ma20 + 2 * std20).iloc[-1]), 4)
        result["BOLL_M"] = round(float(ma20.iloc[-1]), 4)
        result["BOLL_L"] = round(float((ma20 - 2 * std20).iloc[-1]), 4)

    return result


# ──────────────────────────────────────────────
# 宏观与市场数据函数
# ──────────────────────────────────────────────

def _macro_growth(limit: int = 8) -> dict:
    result = {}
    gdp = ak_cache(ak.macro_china_gdp, ttl=86400)
    if gdp is not None and not gdp.empty:
        result["GDP季度"] = _df_to_records(gdp.tail(limit))
    gdp_y = ak_cache(ak.macro_china_gdp_yearly, ttl=86400)
    if gdp_y is not None and not gdp_y.empty:
        result["GDP年率"] = _df_to_records(gdp_y.tail(limit))
    ind = ak_cache(ak.macro_china_industrial_production_yoy, ttl=86400)
    if ind is not None and not ind.empty:
        result["工业增加值同比"] = _df_to_records(ind.tail(limit))
    return result


def _macro_inflation(limit: int = 12) -> dict:
    result = {}
    cpi = ak_cache(ak.macro_china_cpi, ttl=86400)
    if cpi is not None and not cpi.empty:
        result["CPI月度"] = _df_to_records(cpi.tail(limit))
    ppi = ak_cache(ak.macro_china_ppi, ttl=86400)
    if ppi is not None and not ppi.empty:
        result["PPI月度"] = _df_to_records(ppi.tail(limit))
    return result


def _macro_business(limit: int = 12) -> dict:
    result = {}
    pmi = ak_cache(ak.macro_china_pmi, ttl=86400)
    if pmi is not None and not pmi.empty:
        result["制造业PMI"] = _df_to_records(pmi.tail(limit))
    caixin = ak_cache(ak.macro_china_cx_pmi_yearly, ttl=86400)
    if caixin is not None and not caixin.empty:
        result["财新制造业PMI"] = _df_to_records(caixin.tail(limit))
    return result


def _macro_monetary(limit: int = 12) -> dict:
    result = {}
    m2 = ak_cache(ak.macro_china_m2_yearly, ttl=86400)
    if m2 is not None and not m2.empty:
        result["M2货币供应年率"] = _df_to_records(m2.tail(limit))
    shrzgm = ak_cache(ak.macro_china_shrzgm, ttl=86400)
    if shrzgm is not None and not shrzgm.empty:
        result["社会融资规模"] = _df_to_records(shrzgm.tail(limit))
    lpr = ak_cache(ak.macro_china_lpr, ttl=86400)
    if lpr is not None and not lpr.empty:
        result["LPR利率"] = _df_to_records(lpr.tail(limit))
    return result


def _stock_sector_fund_flow_rank(days: str = "今日", cate: str = "行业资金流") -> list:
    df = ak_cache(ak.stock_sector_fund_flow_rank, indicator=days, sector_type=cate, ttl=3600)
    return _df_to_records(df)


def _northbound_funds() -> list:
    df = ak_cache(ak.stock_hsgt_hist_em, symbol="北向资金", ttl=3600)
    if df is not None and not df.empty:
        return _df_to_records(df.tail(10))
    return []


def _margin_balance() -> list:
    df = ak_cache(ak.stock_margin_account_info, ttl=3600)
    if df is not None and not df.empty:
        return _df_to_records(df.tail(30))
    return []


def _sector_valuation() -> list:
    df = ak_cache(ak.sw_index_first_info, ttl=86400)
    if df is not None and not df.empty:
        if "市盈率" in df.columns:
            df["市盈率"] = pd.to_numeric(df["市盈率"], errors="coerce")
            df = df.sort_values("市盈率")
        return _df_to_records(df.head(50))
    return []


def _stock_zt_pool_em(limit: int = 50) -> list:
    date = _recent_trade_date_str()
    df = ak_cache(ak.stock_zt_pool_em, date=date, ttl=3600)
    if df is not None and not df.empty:
        for col in ["序号", "流通市值", "总市值"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        if "成交额" in df.columns:
            df = df.sort_values("成交额", ascending=False)
        return _df_to_records(df.head(limit))
    return []


def _stock_lhb_ggtj_sina(days: str = "5", limit: int = 50) -> list:
    df = ak_cache(ak.stock_lhb_ggtj_sina, symbol=days, ttl=3600)
    if df is not None and not df.empty:
        return _df_to_records(df.head(limit))
    return []


def _option_ivix(limit: int = 30) -> list:
    df = ak_cache(ak.index_option_50etf_qvix, ttl=3600)
    if df is not None and not df.empty:
        return _df_to_records(df.tail(limit))
    return []


def _policy_search(keyword: str, limit: int = 20) -> list:
    """公告/政策关键词扫描。
    注意：akshare 无国务院/央行/发改委政策库，此处用巨潮披露报告做近似覆盖，
    关键词命中"问询/监管/处罚/政策/规划"等监管类公告。暂无国务院/央行/发改委政策库，后续可扩展政策爬虫。
    """
    result = []
    # 1. 巨潮披露报告（含问询函、监管函等）
    df = ak_cache(ak.stock_zh_a_disclosure_report_cninfo,
                  symbol="全部", market="沪深京",
                  category="公司治理", start_date="20240101", ttl=43200)
    if df is not None and not df.empty:
        title_col = "公告标题" if "公告标题" in df.columns else df.columns[2]
        if keyword:
            mask = df[title_col].apply(lambda t: keyword in str(t) if pd.notna(t) else False)
            df = df[mask]
        result.extend(_df_to_records(df.head(limit)))
    # 2. 东方财富公告（补充）
    df2 = ak_cache(ak.stock_notice_report, symbol="全部", date=_recent_trade_date_str(), ttl=3600)
    if df2 is not None and not df2.empty:
        title_col = "公告标题" if "公告标题" in df2.columns else df2.columns[2]
        if keyword:
            mask = df2[title_col].apply(lambda t: keyword in str(t) if pd.notna(t) else False)
            df2 = df2[mask]
        result.extend(_df_to_records(df2.head(limit)))
    return result[:limit]


def _industry_sw_tree(keyword: str = "") -> list:
    """申万行业树"""
    df = ak_cache(ak.sw_index_first_info, ttl=86400)
    if df is None or df.empty:
        return []
    if keyword:
        mask = df["行业名称"].apply(lambda t: keyword in str(t) if pd.notna(t) else False)
        df = df[mask]
    return _df_to_records(df)


def _industry_sw_constituents_detail(industry_code: str, limit: int = 50) -> list:
    """申万行业成分股（复用 industry_sw.get_constituents，统一走健壮的获取路径）"""
    from ...data.sources.industry_sw import get_constituents
    df = get_constituents(industry_code)
    if df is None or df.empty:
        return []
    return _df_to_records(df.head(limit))


def _industry_quotes(industry: str, limit: int = 30) -> dict:
    """行业行情+估值+资金流"""
    result = {}
    # 申万行业指数行情
    df = ak_cache(ak.sw_index_daily, symbol="801010", ttl=3600)
    if df is not None and not df.empty:
        result["行业指数行情"] = _df_to_records(df.tail(limit))
    # 行业估值
    val = ak_cache(ak.sw_index_first_info, ttl=86400)
    if val is not None and not val.empty:
        if industry:
            mask = val["行业名称"].apply(lambda t: industry in str(t) if pd.notna(t) else False)
            val = val[mask]
        result["行业估值"] = _df_to_records(val.head(limit))
    return result


def _industry_capital_flow(industry: str = "", limit: int = 20) -> list:
    """行业资金流排行"""
    df = ak_cache(ak.stock_sector_fund_flow_rank, indicator="今日", sector_type="行业资金流", ttl=3600)
    if df is None or df.empty:
        return []
    if industry and "名称" in df.columns:
        mask = df["名称"].apply(lambda t: industry in str(t) if pd.notna(t) else False)
        df = df[mask]
    return _df_to_records(df.head(limit))


def _sector_rotation() -> list:
    """行业轮动排行"""
    df = ak_cache(ak.stock_sector_fund_flow_rank, indicator="今日", sector_type="行业资金流", ttl=3600)
    if df is None or df.empty:
        return []
    if "今日涨跌幅" in df.columns:
        df["今日涨跌幅"] = pd.to_numeric(df["今日涨跌幅"], errors="coerce")
        df = df.sort_values("今日涨跌幅", ascending=False)
    if "序号" in df.columns:
        df = df.drop(columns=["序号"])
    return _df_to_records(df.head(15))


# ──────────────────────────────────────────────
# 暴雷簇补充数据（独董/关联交易/问询函/担保/诉讼）
# ──────────────────────────────────────────────

def _independent_director(sc: StockCode) -> dict:
    """独立董事信息（通过巨潮关联交易+高管持股接口近似获取）。
    akshare 无独董出席率直接接口，此处返回高管/独董变动记录。
    """
    result = {}
    # 高管持股变动（含独董）
    df = ak_cache(ak.stock_hold_management_person_em, symbol=sc.symbol_pure, ttl=43200)
    if df is not None and not df.empty:
        result["高管持股变动"] = _df_to_records(df.head(20))
    # 高管变动
    mgmt = ak_cache(ak.stock_management_change_ths, symbol=sc.symbol_pure, ttl=43200)
    if mgmt is not None and not mgmt.empty:
        result["高管变动"] = _df_to_records(mgmt.head(20))
    result["note"] = "akshare 无独董出席率直接接口，仅提供高管变动记录"
    return result


def _related_transactions(sc: StockCode) -> dict:
    """关联交易（巨潮关联交易披露）"""
    df = ak_cache(ak.stock_zh_a_disclosure_relation_cninfo,
                  symbol="全部", market="沪深京",
                  start_date="20230101", end_date=datetime.now().strftime("%Y%m%d"), ttl=43200)
    if df is None or df.empty:
        return {"note": "无关联交易披露数据"}
    # 筛选该股票
    code_col = "股票代码" if "股票代码" in df.columns else df.columns[1]
    mask = df[code_col].apply(lambda t: sc.symbol_pure in str(t) if pd.notna(t) else False)
    matched = df[mask]
    return {"关联交易披露": _df_to_records(matched.head(30))}


def _inquiry_letters(sc: StockCode) -> dict:
    """问询函频次（通过巨潮披露报告筛选问询类）"""
    df = ak_cache(ak.stock_zh_a_disclosure_report_cninfo,
                  symbol="全部", market="沪深京",
                  category="公司治理",
                  start_date="20230101", ttl=43200)
    if df is None or df.empty:
        return {"问询函频次": 0, "note": "无披露数据"}
    code_col = "股票代码" if "股票代码" in df.columns else df.columns[1]
    title_col = "公告标题" if "公告标题" in df.columns else df.columns[2]
    # 筛选该股票 + 问询类关键词
    inquiry_keywords = ["问询", "关注函", "监管函", "警示", "处罚", "立案", "整改"]
    mask = df[code_col].apply(lambda t: sc.symbol_pure in str(t) if pd.notna(t) else False)
    matched = df[mask]
    inquiry_mask = matched[title_col].apply(
        lambda t: any(k in str(t) for k in inquiry_keywords) if pd.notna(t) else False
    )
    inquiries = matched[inquiry_mask]
    return {
        "问询函频次": int(len(inquiries)),
        "问询函明细": _df_to_records(inquiries.head(20)),
    }


def _guarantee_and_lawsuit(sc: StockCode) -> dict:
    """对外担保+诉讼（巨潮）"""
    result = {}
    guar = ak_cache(ak.stock_cg_guarantee_cninfo, symbol=sc.symbol_pure, ttl=43200)
    if guar is not None and not guar.empty:
        result["对外担保"] = _df_to_records(guar.head(20))
    lawsuit = ak_cache(ak.stock_cg_lawsuit_cninfo, symbol=sc.symbol_pure, ttl=43200)
    if lawsuit is not None and not lawsuit.empty:
        result["诉讼"] = _df_to_records(lawsuit.head(20))
    return result


def _resolve_sw_code(sector: str) -> str:
    """通过申万行业树查找 sector 对应的申万行业代码（如 "801010"）"""
    if not sector:
        return ""
    df = ak_cache(ak.sw_index_first_info, ttl=86400)
    if df is None or df.empty:
        return ""
    name_col = "行业名称" if "行业名称" in df.columns else df.columns[1]
    code_col = "行业代码" if "行业代码" in df.columns else df.columns[0]
    mask = df[name_col].apply(lambda t: sector in str(t) if pd.notna(t) else False)
    matched = df[mask]
    if matched.empty:
        return ""
    return str(matched.iloc[0][code_col])


# ──────────────────────────────────────────────
# 数据簇主函数
# ──────────────────────────────────────────────

def tech_invest_data(concept: str, symbols: list, start_year: str = "2020") -> dict:
    """
    簇1: 新兴技术投研 —— 一次返回 L1-L7 全链路投研数据。
    输入: concept 概念名(如"钠电池"), symbols 概念股代码列表(如["002812","300073"])
    """
    result = {"concept": concept, "symbols": symbols}

    # 解析所有 StockCode
    sc_list = []
    for s in symbols:
        try:
            sc = resolve_stock_code(s)
            err = None
        except ValueError as e:
            sc, err = None, str(e)
        if err:
            sc_list.append((s, None))
        else:
            sc_list.append((s, sc))

    # L1 技术拆解
    l1 = {"个股信息": {}, "行业分类": [], "申万树": []}
    for s, sc in sc_list:
        l1["个股信息"][s] = _individual_info(sc) if sc else {"error": "代码解析失败"}
    l1["申万树"] = _industry_sw_tree(keyword=concept)
    result["L1_tech_decompose"] = l1

    # L2 成熟度
    l2 = {"财务指标": {}, "报表": {}, "行情": {}}
    for s, sc in sc_list:
        if not sc:
            l2["财务指标"][s] = {"error": "代码解析失败"}
            l2["报表"][s] = {"error": "代码解析失败"}
            l2["行情"][s] = {"error": "代码解析失败"}
            continue
        l2["财务指标"][s] = _financial_indicators(sc, start_year=start_year, limit=20)
        l2["报表"][s] = _financial_statements(sc)
        l2["行情"][s] = _market_prices(sc, limit=60)
    result["L2_maturity"] = l2

    # L3 产业链
    sw_code = _resolve_sw_code(concept)
    l3 = {
        "行业成分股": _industry_sw_constituents_detail(sw_code, limit=50) if sw_code else [],
        "同业对比": {},
    }
    for s, sc in sc_list:
        l3["同业对比"][s] = _peer_comparison(sc) if sc else {"error": "代码解析失败"}
    result["L3_chain"] = l3

    # L4 壁垒
    l4 = {"机构行为": {}}
    for s, sc in sc_list:
        l4["机构行为"][s] = _capital_tracking(sc) if sc else {"error": "代码解析失败"}
    result["L4_moat"] = l4

    # L5 时间线
    l5 = {
        "政策": _policy_search(keyword=concept, limit=20),
        "舆情": {},
    }
    for s, sc in sc_list:
        l5["舆情"][s] = _sentiment_side(sc) if sc else {"error": "代码解析失败"}
    result["L5_timeline"] = l5

    # L6 宏观
    result["L6_macro"] = {
        "增长": _macro_growth(limit=8),
        "景气": _macro_business(limit=12),
        "货币": _macro_monetary(limit=12),
        "估值": _sector_valuation(),
        "主线": {"note": "industry_themes 行业主题聚类待实现"},
    }

    # L7 情绪
    result["L7_sentiment"] = {
        "行业资金流": _stock_sector_fund_flow_rank(days="今日", cate="行业资金流"),
        "北向": _northbound_funds(),
        "周期定位": {"note": "kitchin/juglar/kondratiev 周期引擎待实现"},
        "资产配置建议": {"note": "cycle_allocator 资产配置计算待实现"},
    }

    return result


def anti_fraud_data(symbol: str, concept: str = "") -> dict:
    """
    簇2: 反诈验证 —— 三步交叉验证，复用底层调用结果。
    输入: symbol 股票代码, concept 概念名(用于政策搜索)
    """
    try:
        sc = resolve_stock_code(symbol)
        err = None
    except ValueError as e:
        sc, err = None, str(e)
    if err or sc is None:
        return {"symbol": symbol, "error": f"代码解析失败: {err}"}

    # 一次调用，多步复用
    basic = _individual_info(sc)
    indicators = _financial_indicators(sc, start_year="2020", limit=20)
    statements = _financial_statements(sc)
    # 行情只调一次 limit=120，内部切片省一半网络开销
    prices_full = _market_prices(sc, limit=120)
    prices_60 = prices_full[-60:] if len(prices_full) > 60 else prices_full
    prices_120 = prices_full
    capital = _capital_tracking(sc)
    peer = _peer_comparison(sc)
    sentiment = _sentiment_side(sc)

    return {
        "symbol": symbol,
        "concept": concept,
        "step1_relevance": {
            "基本信息": basic,
            "财务指标": indicators,
            "报表": statements,
        },
        "step2_profile_moat": {
            "股东高管": basic,  # 复用，含主要股东/高管变动
            "财务": indicators,
            "行情": prices_60,
            "机构": capital,
            "同业": peer,
        },
        "step3_cross_check": {
            "舆情": sentiment,
            "资金机构": capital,  # 复用
            "行情长周期": prices_120,
        },
    }


def bl_pathology_data(symbol: str) -> dict:
    """
    簇3: 暴雷病理学 —— 多维度扫描暴雷信号。
    输入: symbol 股票代码
    """
    try:
        sc = resolve_stock_code(symbol)
        err = None
    except ValueError as e:
        sc, err = None, str(e)
    if err or sc is None:
        return {"symbol": symbol, "error": f"代码解析失败: {err}"}

    basic = _individual_info(sc)
    indicators = _financial_indicators(sc, start_year="2018", limit=30)
    statements = _financial_statements(sc)
    sentiment = _sentiment_side(sc)
    capital = _capital_tracking(sc)
    prices_year = _market_prices(sc, limit=250)
    tech = _stock_tech_indicators(sc)
    # 暴雷簇补充：独董/关联交易/问询函/担保诉讼
    ind_dir = _independent_director(sc)
    related = _related_transactions(sc)
    inquiry = _inquiry_letters(sc)
    guar_lawsuit = _guarantee_and_lawsuit(sc)

    # 从 sentiment 中提取审计/人事/公告相关板块
    audit_news = []
    for item in sentiment.get("个股新闻", []):
        title = str(item.get("标题", "")) + str(item.get("内容", ""))
        if any(k in title for k in ["审计", "问询", "警示", "处罚", "违规", "立案", "ST"]):
            audit_news.append(item)

    personnel = {
        "高管变动": basic.get("高管变动", []),
        "股东人数": sentiment.get("股东人数变化", []),
        "独董信息": ind_dir,
    }

    return {
        "symbol": symbol,
        "basic_profile": {
            "基本信息": basic.get("基本信息", {}),
            "十大股东": basic.get("主要股东", []),
            "高管变动": basic.get("高管变动", []),
        },
        "financial_timeseries": {
            "指标86项": indicators.get("财务指标", []),
            "三大报表": statements,
        },
        "audit_signals": {"审计相关新闻": audit_news},
        "personnel_anomaly": personnel,
        "disclosure_scan": {
            "新闻公告": sentiment.get("个股新闻", []),
            "问询函": inquiry,
        },
        "capital_anomaly": {
            "资金流": capital.get("个股资金流", []),
            "机构行为": {
                "机构调研统计": capital.get("机构调研统计", []),
                "机构调研详细": capital.get("机构调研详细", []),
            },
        },
        "price_anomaly": {
            "行情1年": prices_year,
            "技术指标": tech,
        },
        "governance_risk": {
            "关联交易": related,
            "对外担保": guar_lawsuit.get("对外担保", []),
            "诉讼": guar_lawsuit.get("诉讼", []),
        },
    }


def sector_hotness_data(sector: str) -> dict:
    """
    簇4: 板块热度 —— 政策/产业/资金/市场/宏观五维扫描。
    输入: sector 板块/行业名称(如"光伏")
    """
    sw_code = _resolve_sw_code(sector)

    return {
        "sector": sector,
        "policy": {"政策文件": _policy_search(keyword=sector, limit=20)},
        "industry": {
            "行业行情": _industry_quotes(industry=sector, limit=30),
            "行业资金流": _industry_capital_flow(industry=sector),
            "成分股": _industry_sw_constituents_detail(sw_code, limit=50) if sw_code else [],
        },
        "capital": {
            "行业资金排行": _stock_sector_fund_flow_rank(days="今日", cate="行业资金流"),
            "北向": _northbound_funds(),
            "融资融券": _margin_balance(),
        },
        "market": {
            "涨停池": _stock_zt_pool_em(limit=50),
            "龙虎榜": _stock_lhb_ggtj_sina(days="5", limit=50),
        },
        "macro_check": {
            "宏观景气": _macro_business(limit=12),
            "行业估值": _sector_valuation(),
        },
    }


def cycle_rotation_data(fast_mode: bool = True) -> dict:
    """
    簇5: 周期定位+行业轮动+对冲选股 —— 全市场级别。
    输入: fast_mode=True 跳过 DCC+因果（待实现），仅返回 akshare 可获取部分
    """
    return {
        "themes": {"note": "industry_themes 行业主题聚类待实现"},
        "hedge": {"note": "industry_themes_dcc DCC-GARCH 时变相关待实现"},
        "lead_lag": {"note": "industry_themes_causality Granger因果链待实现"},
        "valuation": {
            "行业估值": _sector_valuation(),
            "轮动排行": _sector_rotation(),
        },
        "cycles": {"note": "kitchin/juglar/kondratiev/nesting 四周期引擎待实现"},
        "macro": {
            "增长": _macro_growth(limit=8),
            "通胀": _macro_inflation(limit=12),
            "景气": _macro_business(limit=12),
            "货币": _macro_monetary(limit=12),
        },
        "sentiment": {
            "融资融券": _margin_balance(),
            "恐慌指数": _option_ivix(limit=30),
            "北向": _northbound_funds(),
        },
        "asset_allocation": {"note": "cycle_allocator 资产配置计算待实现"},
        "fast_mode": fast_mode,
    }
