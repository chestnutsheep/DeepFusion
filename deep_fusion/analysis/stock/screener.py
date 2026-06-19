"""Stock screening: multi-factor scoring, momentum/valuation percentile."""
import akshare as ak
import pandas as pd

from ...shared.indicators import add_technical_indicators
from ...shared.utils import ak_cache


def momentum_screen(top_n: int = 30, min_price: float = 3.0) -> str:
    """Screen A-share stocks by short-term momentum (5-day price change > volume).

    Returns:
        str: CSV with symbol, name, price, change%, volume, momentum_score
    """
    spot = ak_cache(ak.stock_zh_a_spot_em, ttl=300, ttl2=600)
    if spot is None or spot.empty:
        return "数据不足"

    df = spot.copy()
    required = ["代码", "名称", "最新价", "涨跌幅"]
    for c in required:
        if c not in df.columns:
            return f"缺少列: {c}，实际有: {list(df.columns)}"

    df = df[df["最新价"] >= min_price].copy()

    df["动量得分"] = df["涨跌幅"].rank(pct=True)

    rename = {"代码": "symbol", "名称": "name", "最新价": "price", "涨跌幅": "change_pct"}
    cols = ["代码", "名称", "最新价", "涨跌幅"]
    if "成交额" in df.columns:
        rename["成交额"] = "volume"
        cols.append("成交额")
    if "换手率" in df.columns:
        cols.append("换手率")
        rename["换手率"] = "turnover"
    cols.append("动量得分")
    rename["动量得分"] = "momentum_score"

    result = df.nlargest(top_n, "涨跌幅")[cols].rename(columns=rename)
    return result.to_csv(index=False, float_format="%.2f")


def volume_breakout(top_n: int = 20, volume_ratio: float = 1.5) -> str:
    """Screen stocks with volume > N x average volume (volume breakout).

    Returns:
        str: CSV with symbol, name, volume_ratio, price, change%
    """
    spot = ak_cache(ak.stock_zh_a_spot_em, ttl=300, ttl2=600)
    if spot is None or spot.empty:
        return "数据不足"

    df = spot.copy()
    required_cols = ["代码", "名称", "最新价", "涨跌幅", "成交量"]
    for c in required_cols:
        if c not in df.columns:
            return f"缺少列: {c}"

    try:
        df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
    except Exception:
        return "成交量列无法转换"

    vol_col = "成交量"
    if "量比" in df.columns:
        df["量比"] = pd.to_numeric(df["量比"], errors="coerce")
        df = df[df["量比"] >= volume_ratio].copy()
        sort_col = "量比"
    else:
        # fallback: estimate volume ratio
        df["量比"] = 1.0
        sort_col = "成交量"

    result = df.nlargest(top_n, sort_col)[
        ["代码", "名称", "最新价", "涨跌幅", "量比", "成交量"]
    ].rename(columns={
        "代码": "symbol", "名称": "name", "最新价": "price",
        "涨跌幅": "change_pct", "量比": "vol_ratio", "成交量": "volume",
    })
    return result.to_csv(index=False, float_format="%.2f")


def technical_signals(symbol: str, period: str = "daily") -> str:
    """Compute technical indicators for a single stock and return signal summary.

    Returns:
        str: formatted CSV with MACD, RSI, KDJ, Bollinger signals
    """

    kline = ak_cache(
        ak.stock_zh_a_hist, symbol=symbol, period=period,
        start_date="19700101", end_date="22220101",
        ttl=3600,
    )
    if kline is None or kline.empty:
        return f"未获取到 {symbol} 的数据"

    col_map = {}
    for c in kline.columns:
        if "日期" in c:
            col_map[c] = "date"
        elif "开盘" in c:
            col_map[c] = "open"
        elif "收盘" in c:
            col_map[c] = "close"
        elif "最高" in c:
            col_map[c] = "high"
        elif "最低" in c:
            col_map[c] = "low"
        elif "成交" in c and "额" not in c:
            col_map[c] = "volume"
    kline.rename(columns=col_map, inplace=True)

    if "close" not in kline.columns:
        return "未找到收盘价数据"

    kline["date"] = pd.to_datetime(kline["date"], errors="coerce")
    kline.set_index("date", inplace=True)
    kline = kline.sort_index()

    add_technical_indicators(
        kline,
        kline["close"],
        kline.get("low"),
        kline.get("high"),
        kline.get("volume"),
    )

    last = kline.iloc[-1]
    signals = {"symbol": symbol, "close": last.get("close")}

    # MACD signals
    if "MACD" in kline.columns and "MACD_signal" in kline.columns:
        macd = last.get("MACD", 0)
        macd_sig = last.get("MACD_signal", 0)
        signals["MACD"] = round(macd, 4)
        signals["MACD_signal"] = round(macd_sig, 4)
        signals["MACD_bullish"] = "Y" if macd > macd_sig else "N"

    # RSI
    if "RSI" in kline.columns:
        rsi = last.get("RSI")
        signals["RSI"] = round(rsi, 2) if rsi else None
        signals["RSI_overbought"] = "Y" if rsi and rsi > 70 else "N"
        signals["RSI_oversold"] = "Y" if rsi and rsi < 30 else "N"

    # KDJ
    if "K" in kline.columns and "D" in kline.columns and "J" in kline.columns:
        signals["KDJ_K"] = round(last.get("K", 0), 2)
        signals["KDJ_D"] = round(last.get("D", 0), 2)
        signals["KDJ_J"] = round(last.get("J", 0), 2)
        signals["KDJ_bullish"] = "Y" if last.get("K", 0) > last.get("D", 0) else "N"

    # Bollinger
    if "Boll_upper" in kline.columns and "Boll_lower" in kline.columns:
        cp = last.get("close", 0)
        up = last.get("Boll_upper", 0)
        dn = last.get("Boll_lower", 0)
        if up != dn:
            signals["Bollinger_pct"] = round((cp - dn) / (up - dn), 3)
            signals["Bollinger_overbought"] = "Y" if cp >= up else "N"
            signals["Bollinger_oversold"] = "Y" if cp <= dn else "N"

    df = pd.DataFrame([signals])
    return df.to_csv(index=False, float_format="%.4f")
