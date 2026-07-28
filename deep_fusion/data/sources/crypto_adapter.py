"""Cryptocurrency market-data adapter.

Implements the contract expected by ``tools/crypto.py`` (Chinese-column
DataFrames / dicts) while sourcing data from free, key-less public APIs:
Binance public REST for candles / long-short / taker-volume / open-interest /
funding-rate / 24h ticker, and alternative.me for the Fear & Greed index.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from ...shared.request import safe_get

_BINANCE_SPOT = "https://api.binance.com"
_BINANCE_FAPI = "https://fapi.binance.com"
_FNG = "https://api.alternative.me/fng/"


def _to_binance_symbol(symbol: str) -> str:
    """Normalise OKX-style ids ('BTC-USDT', 'BTC-USDT-SWAP') / plain ('BTC') to 'BTCUSDT'."""
    s = symbol.strip().upper()
    if s.endswith("-SWAP"):
        s = s[: -len("-SWAP")]
    s = s.replace("-", "").replace("/", "")
    if not s.endswith("USDT"):
        s = s + "USDT"
    return s


def _binance_interval(interval: str) -> str:
    """Map OKX-style granularity ('1H','1D','5m','1M') to Binance ('1h','1d','5m','1M')."""
    if interval.endswith("M"):  # month, keep upper-case
        return interval
    return interval.lower()


def _ts_to_str(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms)


def okx_candles(symbol: str, interval: str = "1D", limit: int = 90) -> pd.DataFrame:
    bs = _to_binance_symbol(symbol)
    bi = _binance_interval(interval)
    res = safe_get(f"{_BINANCE_SPOT}/api/v3/klines",
                   params={"symbol": bs, "interval": bi, "limit": limit}, timeout=20)
    if not res:
        return pd.DataFrame()
    rows = res.json()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        rows,
        columns=["open_time", "open", "high", "low", "close", "volume", "close_time",
                 "qav", "trades", "tbav", "tqav", "ignore"],
    )
    df["时间"] = df["open_time"].map(_ts_to_str)
    df["开盘"] = pd.to_numeric(df["open"], errors="coerce")
    df["最高"] = pd.to_numeric(df["high"], errors="coerce")
    df["最低"] = pd.to_numeric(df["low"], errors="coerce")
    df["收盘"] = pd.to_numeric(df["close"], errors="coerce")
    df["成交量"] = pd.to_numeric(df["volume"], errors="coerce")
    df["成交额"] = pd.to_numeric(df["qav"], errors="coerce")
    return df[["时间", "开盘", "最高", "最低", "收盘", "成交量", "成交额"]]


def okx_sentiment(symbol: str, period: str = "1h", inst_type: str = "SPOT"):
    bs = _to_binance_symbol(symbol)
    bi = _binance_interval(period)
    # 多空持仓比
    lr = safe_get(f"{_BINANCE_FAPI}/futures/data/globalLongShortAccountRatio",
                  params={"symbol": bs, "period": bi, "limit": 30}, timeout=20)
    loan_df = pd.DataFrame()
    if lr:
        rows = lr.json()
        if rows:
            d = pd.DataFrame(rows)
            d["时间"] = d["timestamp"].map(_ts_to_str)
            d["多空比"] = pd.to_numeric(d["longShortRatio"], errors="coerce")
            d["多头占比"] = pd.to_numeric(d["longAccount"], errors="coerce")
            d["空头占比"] = pd.to_numeric(d["shortAccount"], errors="coerce")
            loan_df = d[["时间", "多空比", "多头占比", "空头占比"]]
    # 主动买卖量
    tv = safe_get(f"{_BINANCE_FAPI}/futures/data/takerlongshortVol",
                  params={"symbol": bs, "period": bi, "limit": 30}, timeout=20)
    taker_df = pd.DataFrame()
    if tv:
        rows = tv.json()
        if rows:
            d = pd.DataFrame(rows)
            d["时间"] = d["timestamp"].map(_ts_to_str)
            d["主动买入量"] = pd.to_numeric(d["buyVol"], errors="coerce")
            d["主动卖出量"] = pd.to_numeric(d["sellVol"], errors="coerce")
            taker_df = d[["时间", "主动买入量", "主动卖出量"]]
    return loan_df, taker_df


def okx_funding_rate(inst_id: str) -> dict:
    bs = _to_binance_symbol(inst_id)
    res = safe_get(f"{_BINANCE_FAPI}/fapi/v1/fundingRate", params={"symbol": bs, "limit": 1}, timeout=20)
    if not res:
        return {}
    rows = res.json()
    if not rows:
        return {}
    r = rows[0]
    rate = float(r.get("fundingRate", 0) or 0)
    return {
        "current_rate_pct": rate * 100,
        "next_rate_pct": rate * 100,
        "funding_time": _ts_to_str(r.get("fundingTime")),
        "sentiment": "多头" if rate > 0 else ("空头" if rate < 0 else "中性"),
    }


def okx_open_interest(inst_id: str) -> dict:
    bs = _to_binance_symbol(inst_id)
    res = safe_get(f"{_BINANCE_FAPI}/fapi/v1/openInterest", params={"symbol": bs}, timeout=20)
    if not res:
        return {}
    r = res.json()
    oi = float(r.get("openInterest", 0) or 0)
    return {
        "oi_qty": oi,
        "oi_ccy": oi,
        "ts": _ts_to_str(r.get("time")),
    }


def binance_ai_report(symbol: str) -> str:
    bs = _to_binance_symbol(symbol)
    res = safe_get(f"{_BINANCE_SPOT}/api/v3/ticker/24hr", params={"symbol": bs}, timeout=20)
    if not res:
        return f"未能获取 {symbol} 的市场数据"
    t = res.json()
    try:
        last = float(t["lastPrice"])
        chg = float(t["priceChangePercent"])
        high = float(t["highPrice"])
        low = float(t["lowPrice"])
        vol = float(t["quoteVolume"])
    except (KeyError, TypeError, ValueError):
        return f"未能解析 {symbol} 的市场数据"
    tone = "偏多" if chg > 0 else ("偏空" if chg < 0 else "震荡")
    return (
        f"--- {symbol} 市场速览 (Binance) ---\n"
        f"最新价: {last:,.2f} USDT\n"
        f"24h 涨跌: {chg:+.2f}%\n"
        f"24h 最高/最低: {high:,.2f} / {low:,.2f}\n"
        f"24h 成交额: {vol:,.0f} USDT\n"
        f"市场情绪: {tone}"
    )


def fear_greed_index(limit: int = 30) -> pd.DataFrame:
    res = safe_get(f"{_FNG}?limit={limit}", timeout=20)
    if not res:
        return pd.DataFrame()
    payload = res.json().get("data", [])
    if not payload:
        return pd.DataFrame()
    df = pd.DataFrame(payload)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s").dt.strftime("%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["value_classification"] = df["value_classification"]
    return df[["value", "value_classification", "timestamp"]]
