"""Akshare data adapter: centralized caching, retry & column normalization.

All akshare calls should go through this adapter, NOT accessed directly as `ak.xxx`.
"""
from __future__ import annotations

from typing import Callable

import akshare as ak
import pandas as pd

from ...cache import ak_cache


# ── 通用接口 ────────────────────────────────────────


def ak_fetch(fn: Callable, *args, key: str | None = None, ttl: int = 86400, **kwargs) -> pd.DataFrame | None:
    """Generic cached akshare fetch.

    Thin wrapper on ak_cache for callers that prefer a uniform interface.
    """
    return ak_cache(fn, *args, key=key, ttl=ttl, **kwargs)


# ── 股票 ─────────────────────────────────────────────

def stock_spot_all(ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_zh_a_spot_em, ttl=ttl)


def stock_hist(symbol: str, period: str = "daily", start: str = "19700101", end: str = "22220101",
               ttl: int = 3600) -> pd.DataFrame | None:
    return ak_cache(ak.stock_zh_a_hist, symbol=symbol, period=period, start_date=start, end_date=end, ttl=ttl)


def stock_minute(symbol: str, period: str = "5", ttl: int = 3600) -> pd.DataFrame | None:
    return ak_cache(ak.stock_zh_a_hist_min_em, symbol=symbol, period=period, ttl=ttl)


def stock_pre_min(symbol: str, ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_zh_a_hist_pre_min_em, symbol=symbol, ttl=ttl)


def stock_intraday(symbol: str, ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_intraday_em, symbol=symbol, ttl=ttl)


def stock_info(symbol: str, ttl: int = 43200) -> pd.DataFrame | None:
    return ak_cache(ak.stock_individual_info_em, symbol=symbol, ttl=ttl)


def stock_holders(symbol: str, ttl: int = 43200) -> pd.DataFrame | None:
    return ak_cache(ak.stock_main_stock_holder, stock=symbol, ttl=ttl)


def stock_management(symbol: str, ttl: int = 43200) -> pd.DataFrame | None:
    return ak_cache(ak.stock_management_change_ths, symbol=symbol, ttl=ttl)


def stock_dividend(symbol: str, ttl: int = 43200) -> pd.DataFrame | None:
    return ak_cache(ak.stock_dividend_cninfo, symbol=symbol, ttl=ttl)


def stock_board_spot(board: str = "东方财富", ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_board_industry_spot_em, ttl=ttl)


def stock_board_hist(symbol: str, period: str = "daily", ttl: int = 3600) -> pd.DataFrame | None:
    return ak_cache(ak.stock_board_industry_hist_em, symbol=symbol, period=period, ttl=ttl)


def stock_board_classify(source: str = "ths", ttl: int = 86400) -> pd.DataFrame | None:
    fn = {"ths": ak.stock_board_industry_name_ths, "cninfo": ak.stock_industry_category_cninfo}.get(source,
                                                                                                    ak.stock_board_industry_name_ths)
    return ak_cache(fn, ttl=ttl)


def stock_fund_flow(ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_sector_fund_flow_rank, indicator="今日", ttl=ttl)


def stock_fund_flow_industry(ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.stock_fund_flow_industry, ttl=ttl)


# ── 基金 ─────────────────────────────────────────────

def fund_open_info(symbol: str, ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.fund_open_fund_info_em, symbol=symbol, ttl=ttl)


def fund_open_daily(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.fund_open_fund_daily_em, ttl=ttl)


def fund_hold(symbol: str, date: str, ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.fund_portfolio_hold_em, symbol=symbol, date=date, ttl=ttl)


def fund_rank(fund_type: str, ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.fund_open_fund_rank_em, symbol=fund_type, ttl=ttl)


# ── 期货 ─────────────────────────────────────────────

def futures_main(symbol: str, ttl: int = 86400) -> pd.DataFrame | None:
    """futures_main_sina expects 新浪品种编号 (e.g. "RB0"), NOT Chinese name or contract code."""
    return ak_cache(ak.futures_main_sina, symbol=symbol, ttl=ttl)


def futures_inventory(symbol: str, ttl: int = 86400) -> pd.DataFrame | None:
    """futures_inventory_em expects Chinese name (e.g. "螺纹钢"), NOT contract code."""
    return ak_cache(ak.futures_inventory_em, symbol=symbol, ttl=ttl)


def futures_spot_price(date: str, vars_list: list, ttl: int = 86400) -> pd.DataFrame | None:
    """futures_spot_price expects contract code list (e.g. ["RB"]), NOT Chinese name."""
    return ak_cache(ak.futures_spot_price, date=date, vars_list=vars_list, ttl=ttl)


def futures_hold(symbol: str, contract: str, date: str, ttl: int = 86400) -> pd.DataFrame | None:
    """futures_hold_pos_sina: symbol is position type (成交量/多单持仓/空单持仓), contract is contract code."""
    return ak_cache(ak.futures_hold_pos_sina, symbol=symbol, contract=contract, date=date, ttl=ttl)


# ── 外汇 ─────────────────────────────────────────────

def fx_spot(ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.fx_spot_quote, ttl=ttl)


def fx_pair(ttl: int = 300) -> pd.DataFrame | None:
    return ak_cache(ak.fx_pair_quote, ttl=ttl)


# ── 宏观 ─────────────────────────────────────────────

def macro_gdp(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_gdp, ttl=ttl)


def macro_cpi(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_cpi, ttl=ttl)


def macro_pmi(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_pmi, ttl=ttl)


def macro_m2(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_m, ttl=ttl)


def macro_lpr(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_lpr, ttl=ttl)


def macro_industrial_yoy(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.macro_china_industrial_production_yoy, ttl=ttl)


# ── 行业 ─────────────────────────────────────────────

def industry_valuation(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.stock_industry_valuation_em, ttl=ttl)


def industry_financial(ttl: int = 86400) -> pd.DataFrame | None:
    return ak_cache(ak.stock_industry_financial_em, ttl=ttl)
