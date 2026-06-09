import numpy as np
import pandas as pd


def add_technical_indicators(
    df: pd.DataFrame,
    close_col: str = "收盘",
    low_col: str = "最低",
    high_col: str = "最高",
    volume_col: str = "成交量",
) -> None:
    if df is None or df.empty:
        return

    close = df[close_col].astype(float)
    low = df[low_col].astype(float)
    high = df[high_col].astype(float)
    volume = df[volume_col].astype(float) if volume_col in df.columns else None

    add_macd(df, close)
    add_kdj(df, close, low, high)
    add_rsi(df, close)
    add_bollinger(df, close)
    add_ema(df, close)
    add_sma(df, close, low, high, volume)
    add_williams_r(df, close, low, high)
    add_cci(df, close, low, high)
    add_obv(df, close, volume)
    add_abv(df, close, volume)
    add_sar(df, close, low, high)
    add_roc(df, close)
    add_psy(df, close)
    add_bias(df, close)
    add_mtm(df, close)


def add_macd(df: pd.DataFrame, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    df["MACD"] = macd
    df["DIF"] = dif
    df["DEA"] = dea


def add_kdj(df: pd.DataFrame, close: pd.Series, low: pd.Series, high: pd.Series, n: int = 9) -> None:
    lowest_low = low.rolling(window=n).min()
    highest_high = high.rolling(window=n).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    df["KDJ.K"] = k
    df["KDJ.D"] = d
    df["KDJ.J"] = j


def add_rsi(df: pd.DataFrame, close: pd.Series, period: int = 14) -> None:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    df["RSI"] = rsi


def add_bollinger(df: pd.DataFrame, close: pd.Series, period: int = 20, std_dev: int = 2) -> None:
    ma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    df["BOLL.U"] = ma + std_dev * std
    df["BOLL.M"] = ma
    df["BOLL.L"] = ma - std_dev * std


def add_ema(df: pd.DataFrame, close: pd.Series, periods: list[int] | None = None) -> None:
    periods = periods or [5, 10, 20, 60]
    for p in periods:
        df[f"EMA.{p}"] = close.ewm(span=p, adjust=False).mean()


def add_sma(df: pd.DataFrame, close: pd.Series, low: pd.Series, high: pd.Series, volume: pd.Series | None = None) -> None:
    for p in [5, 10, 20, 60]:
        df[f"MA.{p}"] = close.rolling(window=p).mean()
    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.ewm(span=14, adjust=False).mean()
    df["ATR14"] = atr14
    up_move = (high - high.shift(1)).fillna(0)
    down_move = (low.shift(1) - low).fillna(0)
    plus_dm = up_move.where(up_move > down_move, 0)
    minus_dm = down_move.where(down_move > up_move, 0)
    di_plus14 = 100 * plus_dm.ewm(span=14, adjust=False).mean() / atr14
    di_minus14 = 100 * minus_dm.ewm(span=14, adjust=False).mean() / atr14
    dx14 = ((di_plus14 - di_minus14).abs() / (di_plus14 + di_minus14)).fillna(0) * 100
    adx14 = dx14.ewm(span=14, adjust=False).mean()
    df["ADX"] = adx14
    df["DI+"] = di_plus14
    df["DI-"] = di_minus14


def add_williams_r(df: pd.DataFrame, close: pd.Series, low: pd.Series, high: pd.Series, period: int = 14) -> None:
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, float("inf"))
    df["WILLIAMS_R"] = wr


def add_cci(df: pd.DataFrame, close: pd.Series, low: pd.Series, high: pd.Series, period: int = 20) -> None:
    tp = (high + low + close) / 3
    ma = tp.rolling(window=period).mean()
    md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - ma) / (0.015 * md.replace(0, float("inf")))
    df["CCI"] = cci


def add_obv(df: pd.DataFrame, close: pd.Series, volume: pd.Series | None) -> None:
    if volume is None:
        return
    direction = close.diff().fillna(0)
    signed_volume = direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)) * volume
    df["OBV"] = signed_volume.cumsum()


def add_abv(
    df: pd.DataFrame, close: pd.Series, volume: pd.Series | None,
    fast: int = 5, mid: int = 10, slow: int = 20,
) -> None:
    if volume is None:
        return
    direction = close.diff().fillna(0)
    signed_volume = direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)) * volume
    obv_line = signed_volume.cumsum()
    abv = obv_line.ewm(span=slow, adjust=False).mean()
    df["ABV"] = abv
    df["ABV.MA5"] = abv.rolling(window=fast).mean()
    df["ABV.MA10"] = abv.rolling(window=mid).mean()


def add_sar(df: pd.DataFrame, close: pd.Series, low: pd.Series, high: pd.Series, acceleration: float = 0.02, max_acc: float = 0.20) -> None:
    length = len(close)
    sar = np.empty(length)
    sar[:] = np.nan
    ep = np.empty(length)
    af = np.empty(length)
    trend = np.empty(length, dtype=bool)

    if length < 3:
        df["SAR"] = pd.Series(sar)
        return

    sar[0] = low.iloc[0]
    ep[0] = high.iloc[0]
    af[0] = acceleration
    trend[0] = True

    for i in range(1, length):
        trend[i] = trend[i - 1]
        if trend[i]:
            sar[i] = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
            sar[i] = min(sar[i], low.iloc[i - 1], low.iloc[i - 2]) if i >= 2 else min(sar[i], low.iloc[i - 1])
            if low.iloc[i] < sar[i]:
                trend[i] = False
                sar[i] = ep[i - 1]
                ep[i] = low.iloc[i]
                af[i] = acceleration
            else:
                if high.iloc[i] > ep[i - 1]:
                    ep[i] = high.iloc[i]
                    af[i] = min(af[i - 1] + acceleration, max_acc)
                else:
                    ep[i] = ep[i - 1]
                    af[i] = af[i - 1]
        else:
            sar[i] = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
            sar[i] = max(sar[i], high.iloc[i - 1], high.iloc[i - 2]) if i >= 2 else max(sar[i], high.iloc[i - 1])
            if high.iloc[i] > sar[i]:
                trend[i] = True
                sar[i] = ep[i - 1]
                ep[i] = high.iloc[i]
                af[i] = acceleration
            else:
                if low.iloc[i] < ep[i - 1]:
                    ep[i] = low.iloc[i]
                    af[i] = min(af[i - 1] + acceleration, max_acc)
                else:
                    ep[i] = ep[i - 1]
                    af[i] = af[i - 1]

    df["SAR"] = pd.Series(sar)


def add_roc(df: pd.DataFrame, close: pd.Series, period: int = 12) -> None:
    roc = (close / close.shift(period) - 1) * 100
    df["ROC"] = roc


def add_psy(df: pd.DataFrame, close: pd.Series, period: int = 12) -> None:
    up_count = close.diff().gt(0).rolling(window=period).sum()
    psy = up_count / period * 100
    df["PSY"] = psy


def add_bias(df: pd.DataFrame, close: pd.Series, periods: list[int] | None = None) -> None:
    periods = periods or [6, 12, 24]
    for p in periods:
        ma = close.rolling(window=p).mean()
        bias = (close - ma) / ma.replace(0, float("inf")) * 100
        df[f"BIAS.{p}"] = bias


def add_mtm(df: pd.DataFrame, close: pd.Series, period: int = 12) -> None:
    mtm = close - close.shift(period)
    df["MTM"] = mtm
