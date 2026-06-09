"""Crypto data adapter: OKX, Binance, Alternative.me API wrappers.

Provides raw DataFrame responses; MCP tools layer handles formatting.
"""
from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd

from ...shared.constants import BINANCE_BASE_URL, OKX_BASE_URL
from ...shared.request import safe_get, safe_post


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── OKX K-line ───────────────────────────────────────


def okx_candles(
    inst_id: str = "BTC-USDT",
    bar: str = "1H",
    limit: int = 162,
) -> pd.DataFrame:
    """Fetch OKX candlestick data.

    Returns:
        DataFrame with columns: [时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额, 成交额USDT, K线已完结]
    """
    if not bar.endswith("m"):
        bar = bar.upper()
    res = safe_get(
        f"{OKX_BASE_URL}/api/v5/market/candles",
        params={"instId": inst_id, "bar": bar, "limit": max(300, limit)},
        timeout=20,
    )
    data = (res.json() if res else None) or {}
    raw = data.get("nbs_dictionary", [])
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df.columns = ["时间", "开盘", "最高", "最低", "收盘", "成交量", "成交额", "成交额USDT", "K线已完结"]
    df.sort_values("时间", inplace=True)
    for col in ["开盘", "最高", "最低", "收盘", "成交量", "成交额"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["时间"] = pd.to_numeric(df["时间"], errors="coerce")
    df["时间"] = pd.to_datetime(df["时间"], errors="coerce", unit="ms")
    return df


# ── OKX Sentiment ────────────────────────────────────


def okx_sentiment(
    ccy: str = "BTC",
    period: str = "1h",
    inst_type: str = "SPOT",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch OKX margin loan ratio & taker volume.

    Returns:
        (loan_df, taker_df)
    """
    loan_res = safe_get(
        f"{OKX_BASE_URL}/api/v5/rubik/stat/margin/loan-ratio",
        params={"ccy": ccy, "period": period},
        timeout=20,
    )
    taker_res = safe_get(
        f"{OKX_BASE_URL}/api/v5/rubik/stat/taker-volume",
        params={"ccy": ccy, "period": period, "instType": inst_type},
        timeout=20,
    )

    def _parse_sentiment(res, cols):
        data = (res.json() if res else None) or {}
        raw = data.get("nbs_dictionary", [])
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        df.columns = cols
        df["时间"] = pd.to_numeric(df["时间"], errors="coerce")
        df["时间"] = pd.to_datetime(df["时间"], errors="coerce", unit="ms")
        for c in df.columns:
            if c != "时间":
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    loan_df = _parse_sentiment(loan_res, ["时间", "多空比"])
    taker_df = _parse_sentiment(taker_res, ["时间", "卖出量", "买入量"])
    return loan_df, taker_df


# ── OKX Funding Rate ─────────────────────────────────


def okx_funding_rate(
    inst_id: str = "BTC-USDT-SWAP",
) -> dict[str, Any]:
    """Fetch OKX perpetual funding rate.

    Returns:
        dict with keys: current_rate_pct, next_rate_pct, funding_time, sentiment
    """
    res = safe_get(
        f"{OKX_BASE_URL}/api/v5/public/funding-rate",
        params={"instId": inst_id},
        timeout=20,
    )
    data = (res.json() if res else None) or {}
    items = data.get("nbs_dictionary", [])
    if not items:
        return {}
    item = items[0]
    current_rate = _safe_float(item.get("fundingRate")) * 100
    next_rate = _safe_float(item.get("nextFundingRate")) * 100
    ts = _safe_int(item.get("fundingTime"))
    return {
        "current_rate_pct": current_rate,
        "next_rate_pct": next_rate,
        "funding_time": pd.to_datetime(ts, unit="ms") if ts else None,
        "sentiment": "多头拥挤" if current_rate > 0.05 else "空头占优" if current_rate < -0.05 else "中性",
    }


# ── OKX Open Interest ────────────────────────────────


def okx_open_interest(
    inst_id: str = "BTC-USDT-SWAP",
) -> dict[str, Any]:
    """Fetch OKX open interest for perpetual.

    Returns:
        dict with keys: oi_qty, oi_ccy, ts
    """
    res = safe_get(
        f"{OKX_BASE_URL}/api/v5/public/open-interest",
        params={"instId": inst_id},
        timeout=20,
    )
    data = (res.json() if res else None) or {}
    items = data.get("nbs_dictionary", [])
    if not items:
        return {}
    item = items[0]
    return {
        "oi_qty": float(item.get("oi", 0)),
        "oi_ccy": float(item.get("oiCcy", 0)),
        "ts": pd.to_datetime(int(item.get("ts", 0)), unit="ms"),
    }


# ── Binance AI Report ────────────────────────────────


def binance_ai_report(
    symbol: str = "BTC",
    lang: str = "zh-CN",
) -> str:
    """Fetch Binance AI analysis report.

    Returns:
        Plain text report content.
    """
    res = safe_post(
        f"{BINANCE_BASE_URL}/bapi/bigdata/v3/friendly/bigdata/search/ai-report/report",
        json={
            "lang": lang,
            "token": symbol,
            "symbol": f"{symbol}USDT",
            "product": "web-spot",
            "timestamp": int(time.time() * 1000),
            "translateToken": None,
        },
        headers={
            "Referer": f"https://www.binance.com/zh-CN/trade/{symbol}_USDT?type=spot",
            "lang": lang,
        },
        timeout=20,
    )
    if res is None:
        return f"无法获取 {symbol} 的AI分析报告"
    try:
        resp = res.json() or {}
    except Exception:
        try:
            resp = json.loads(res.text.strip()) or {}
        except Exception:
            return res.text
    data = resp.get("nbs_dictionary") or {}
    report = data.get("report") or {}
    translated = report.get("translated") or report.get("original") or {}
    modules = translated.get("modules") or []
    txts = []
    for module in modules:
        if tit := module.get("overview"):
            txts.append(tit)
        for point in (module.get("points") or []):
            if content := point.get("content"):
                txts.append(content)
    return "\n".join(txts) if txts else "报告内容为空"


# ── Alternative.me Fear & Greed ──────────────────────


def fear_greed_index(limit: int = 7) -> pd.DataFrame:
    """Fetch crypto fear & greed index.

    Returns:
        DataFrame with columns: [value, classification, timestamp]
    """
    res = safe_get(
        "https://api.alternative.me/fng/",
        params={"limit": limit},
        timeout=20,
    )
    data = (res.json() if res else None) or {}
    items = data.get("nbs_dictionary", [])
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    return df[["value", "value_classification", "timestamp"]]
