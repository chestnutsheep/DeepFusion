"""新浪/腾讯直连行情取数（不依赖东方财富、不依赖代理）。

背景：当前网络环境下东方财富(eastmoney)与通达信(7709)出口均不可达，
而新浪(hq.sinajs.cn / quotes.sina.cn)与腾讯(qt.gtimg.cn / ifzq.gtimg.cn)直连稳定可达。
本模块提供与 akshare 等价的轻量取数函数，供个股面板实时报价/分钟线/分笔使用。

注意：本模块只做"行情通道"替换，不改动任何计算定义（数值口径/信号公式不变）。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

try:
    import pandas as pd
except Exception:  # pandas 为可选依赖，仅在日K函数用到
    pd = None

import requests

_LOGGER = logging.getLogger(__name__)

# 直连，不走代理（新浪/腾讯行情不受代理开关影响，避免代理不可达时整链路失败）
_PROXIES = {"http": None, "https": None}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}
_TIMEOUT = 12


def _get(url: str, timeout: int = _TIMEOUT) -> Optional[requests.Response]:
    try:
        return requests.get(url, headers=_HEADERS, proxies=_PROXIES, timeout=timeout)
    except Exception as exc:  # 网络问题直接返回 None，不抛不重试用
        _LOGGER.warning("直连行情失败 %s: %s", url[:60], exc)
        return None


def _market_prefix(symbol: str, market: str = "") -> str:
    """返回 (市场前缀, 带市场代码)。symbol 为 6 位代码。"""
    if market:
        mkt = market.lower()
    else:
        mkt = "sh" if symbol.startswith(("6", "9")) else "sz"
        if symbol.startswith(("4", "8")):
            mkt = "bj"
    return mkt, f"{mkt}{symbol}"


def sina_realtime(symbol: str, market: str = "") -> Optional[dict]:
    """新浪实时报价 hq.sinajs.cn。返回 dict 或 None。

    字段：name/price/open/prev_close/high/low/amount/volume/turnover(无→None)/...
    """
    _, code = _market_prefix(symbol, market)
    r = _get(f"https://hq.sinajs.cn/list={code}")
    if not r or r.status_code != 200:
        return None
    text = r.text
    # 形如 var hq_str_sh600519="1,贵州茅台,...";
    if "=" not in text or '"' not in text:
        return None
    payload = text.split("=", 1)[1].strip().strip(";").strip('"')
    parts = payload.split(",")
    if len(parts) < 32:
        return None
    try:
        price = float(parts[3])
    except (ValueError, IndexError):
        return None
    return {
        "symbol": symbol,
        "name": parts[0],
        "price": price,
        "prev_close": _to_float(parts[2]),
        "open": _to_float(parts[1]),
        "high": _to_float(parts[4]),
        "low": _to_float(parts[5]),
        "volume": _to_float(parts[8]),  # 股
        "amount": _to_float(parts[9]),  # 元
        "turnover": None,  # 新浪实时不含换手率
        "pe": None,
        "pb": None,
        "total_mv": None,
        "float_mv": None,
        "volume_ratio": None,
        "source": "sina",
    }


def tencent_realtime(symbol: str, market: str = "") -> Optional[dict]:
    """腾讯实时 qt.gtimg.cn。返回 dict 或 None。

    字段丰富，含最新价/涨跌/换手率，但无 PE/PB/市值/量比。
    """
    _, code = _market_prefix(symbol, market)
    r = _get(f"https://qt.gtimg.cn/q={code}")
    if not r or r.status_code != 200:
        return None
    text = r.text
    if "=" not in text or '"' not in text:
        return None
    payload = text.split("=", 1)[1].strip().strip(";").strip('"')
    parts = payload.split("~")
    if len(parts) < 46:
        return None
    try:
        price = float(parts[3])
    except (ValueError, IndexError):
        return None
    prev_close = _to_float(parts[4])
    change = price - prev_close if prev_close is not None else None
    return {
        "symbol": symbol,
        "name": parts[1],
        "price": price,
        "prev_close": prev_close,
        "open": _to_float(parts[5]),
        "high": _to_float(parts[33]),
        "low": _to_float(parts[34]),
        "volume": _to_float(parts[36]),  # 股（手×100 近似）
        "amount": _to_float(parts[37]),  # 千元
        "turnover": _to_float(parts[38]),  # 换手率 %
        "pe": None,
        "pb": None,
        "total_mv": None,
        "float_mv": None,
        "volume_ratio": None,
        "source": "tencent",
        # 备用：涨跌额/涨跌幅
        "change": change,
        "change_pct": _to_float(parts[32]),
    }


def tencent_minute_kline(symbol: str, minute_period: str = "5", market: str = "") -> Optional[list]:
    """腾讯分钟线 ifzq.gtimg.cn（不带 web 前缀，已验证可达）。

    返回 list[dict{time,open,close,high,low,volume}] 或 None。
    """
    _, code = _market_prefix(symbol, market)
    mk_key = f"m{minute_period}"
    r = _get(
        f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{mk_key},,"
        f"{min(480, int(minute_period) * 240)}"
    )
    if not r or r.status_code != 200:
        return None
    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("code") != 0:
        return None
    node = data.get("data", {}).get(code, {})
    if not isinstance(node, dict):
        return None
    # mkline 结构: data[code] = {"qt": {...}, "m5": [[time,open,close,high,low,volume], ...]}
    series = node.get(mk_key)
    if not series:
        return None
    out = []
    for row in series:
        # row: [time, open, close, high, low, volume]
        if len(row) < 6:
            continue
        out.append({
            "time": row[0],
            "open": _to_float(row[1]),
            "close": _to_float(row[2]),
            "high": _to_float(row[3]),
            "low": _to_float(row[4]),
            "volume": _to_float(row[5]),
        })
    return out or None


def tencent_daily_kline(
        symbol: str, market: str = "", limit: int = 365, adjust: str = "qfq"
) -> Optional[pd.DataFrame]:
    """腾讯日K线 ifzq.gtimg.cn（直连，已验证可达）。

    替代 akshare stock_zh_a_daily（在 serve 走代理时不可达）。
    返回 pd.DataFrame，列: date/open/close/high/low/volume，按日期升序；失败返回 None。
    """
    if "pd" not in globals():
        import pandas as pd  # noqa: F401（仅本函数惰性依赖）
    else:
        pd = globals()["pd"]
    _, code = _market_prefix(symbol, market)
    adj = "qfq" if adjust in ("qfq", "forward") else ("hfq" if adjust in ("hfq", "backward") else "")
    # 腾讯日K接口：day=日线，qfqday=前复权，hfqday=后复权
    day_key = f"{adj}day" if adj else "day"
    r = _get(f"https://ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{limit},{adj}")
    if not r or r.status_code != 200:
        return None
    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("code") != 0:
        return None
    node = data.get("data", {}).get(code, {})
    if not isinstance(node, dict):
        return None
    series = node.get(day_key) or node.get("qfqday") or node.get("day") or node.get("hfqday")
    if not series:
        return None
    rows = []
    for row in series:
        # row: [date, open, close, high, low, volume, ...]
        if len(row) < 6:
            continue
        rows.append({
            "date": row[0],
            "open": _to_float(row[1]),
            "close": _to_float(row[2]),
            "high": _to_float(row[3]),
            "low": _to_float(row[4]),
            "volume": _to_float(row[5]),
        })
    if not rows:
        return None
    df = pd.DataFrame(rows)
    return df


def sina_intraday(symbol: str, market: str = "", datalen: int = 240) -> Optional[list]:
    """新浪分时/分钟线 quotes.sina.cn（已验证可达），用于分笔/盘前替代。

    返回 list[dict{day,open,high,low,close,volume}] 或 None。
    """
    _, code = _market_prefix(symbol, market)
    r = _get(
        f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
        f"?symbol={code}&scale=1&ma=no&datalen={datalen}"
    )
    if not r or r.status_code != 200:
        return None
    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, list):
        return None
    out = []
    for row in data:
        out.append({
            "time": row.get("day"),
            "open": _to_float(row.get("open")),
            "close": _to_float(row.get("close")),
            "high": _to_float(row.get("high")),
            "low": _to_float(row.get("low")),
            "volume": _to_float(row.get("volume")),
        })
    return out or None


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None
    except (ValueError, TypeError):
        return None
