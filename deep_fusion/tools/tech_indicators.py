"""股票技术指标工具 — 从 individual_hist K线数据计算衍生指标。"""
from __future__ import annotations

import json

import akshare as ak
import pandas as pd

from ..cache import CacheKey, ak_cache
from ..server import mcp
from ..shared.indicators import add_technical_indicators


def fetch_kline(symbol: str, period: str = "daily") -> pd.DataFrame | None:
    """获取股票 K 线，按项目权威数据源优先级降级取数：
    通达信 > 腾讯 > 新浪 > 同花顺 > 东方财富。

    统一经 ``data/sources/quote_priority`` 的 ``fetch_stock_daily_priority``
    （首个可达且非空的源生效），不改动任何计算口径。返回 akshare 风格的
    列（trade_date/open/close/high/low/volume），与下游 add_technical_indicators 一致。
    """
    from ..data.sources.quote_priority import fetch_stock_daily_priority

    rows, src = fetch_stock_daily_priority(symbol, days_back=800)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "date": "trade_date", "open": "open", "close": "close",
        "high": "high", "low": "low", "volume": "volume",
    })
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
    df = df.sort_values("trade_date")
    return df


@mcp.tool(
    name="stock_tech_indicators",
    description="计算 A 股技术指标：MACD/KDJ/RSI/布林带/均线/ADX/CCI/OBV/SAR/WR/ROC/PSY/BIAS/MTM。默认返回最新一期JSON；return_series=True 返回最近 window 期的指标序列（用于绘制符合图形）",
)
def stock_tech_indicators(
        symbol: str,
        period: str = "daily",
        return_series: bool = False,
        window: int = 120,
) -> str:
    """获取指定股票的技术指标。

    - return_series=False（默认）：返回最新一期标量 JSON。
    - return_series=True：返回最近 window 期的逐期指标序列 JSON（含 trade_date），
      供前端绘制 MACD/KDJ/DMI/BOLL 等 subplot。

    指标结果按 (symbol, period) 缓存；K 线数据本身已有 ak_cache 缓存。
    """
    df = fetch_kline(symbol, period)
    if df is None or df.empty:
        return json.dumps({"error": f"无法获取 {symbol} 的 K 线数据"})

    add_technical_indicators(
        df, close_col="close", low_col="low",
        high_col="high", volume_col="volume",
    )

    cols = [
        "trade_date", "close", "open", "high", "low", "volume",
        "MACD", "DIF", "DEA",
        "KDJ.K", "KDJ.D", "KDJ.J",
        "RSI",
        "BOLL.U", "BOLL.M", "BOLL.L",
        "MA.5", "MA.10", "MA.20", "MA.60",
        "EMA.5", "EMA.10", "EMA.20",
        "ATR14", "ADX", "DI+", "DI-",
        "CCI", "WILLIAMS_R", "ROC",
        "OBV", "PSY", "BIAS", "MTM",
        "SAR",
    ]

    if return_series:
        _ck = CacheKey.init(
            f"tech_indicators_series_{symbol}_{period}_v1",
            ttl=3600, ttl2=7200,
        )
        cached = _ck.get()
        if cached is not None and isinstance(cached, str):
            return cached
        tail = df.tail(max(10, window))
        records = []
        for _, row in tail.iterrows():
            rec = {}
            for c in cols:
                if c in tail.columns:
                    v = row[c]
                    rec[c] = round(float(v), 4) if isinstance(v, (int, float)) else None
            records.append(rec)
        text = json.dumps(
            {"symbol": symbol, "period": period, "series": records},
            ensure_ascii=False,
        )
        _ck.set(text)
        return text

    # 默认：最新一期标量
    _ck = CacheKey.init(
        f"tech_indicators_{symbol}_{period}_v1",
        ttl=3600, ttl2=7200,
    )
    cached = _ck.get()
    if cached is not None and isinstance(cached, str):
        return cached

    latest = df.tail(1)
    if latest.empty:
        return json.dumps({"error": "计算后无数据"})

    result = {}
    for c in cols:
        if c in latest.columns:
            v = latest.iloc[0][c]
            result[c] = round(float(v), 4) if isinstance(v, (int, float)) else str(v)

    result["symbol"] = symbol
    result["period"] = period
    text = json.dumps(result, ensure_ascii=False)
    _ck.set(text)
    return text
