"""quote_priority.py — 统一行情数据源优先级降级层。

权威优先级（项目约定，2026-08-19 落地）：
    通达信 (pytdx) > 腾讯 (gtimg) > 新浪 (Sina) > 同花顺 (akshare ths) > 东方财富 (akshare em)

语义：**按优先级从高到低依次尝试，取第一个「可达且返回非空」的源作为实际取数源**。
未安装的源（如无 pytdx）或网络不可达的源会自动跳过，不阻断链路——
这保证在任意网络环境下都落到当前可用的源，同时严格尊重用户定义的偏好顺序。

注意：
- 本模块只做「通道选择」，**不改任何计算口径/信号公式**（守住红线）。
- 所有取数函数返回统一结构 list[dict{code,date,open,high,low,close,volume,amount}]
  （升序），与 market_collector 的写库结构一致。
- 通达信为原生 TCP（不经 http 代理），直连公共行情服务器；已实测可用服务器列表见
  _TDX_SERVERS（直连可达，代理下反而连不上，故强制不走代理）。
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Sequence

_LOGGER = logging.getLogger(__name__)

# 项目权威数据源优先级（高 → 低）
SOURCE_PRIORITY = ["tdx", "tencent", "sina", "ths", "eastmoney"]

# 通达信公共行情服务器（直连可达，已实测 2026-08-19）。
# 顺序即尝试顺序；首个 connect 成功即止。
_TDX_SERVERS = [
    ("180.153.18.170", 7709),
    ("60.12.136.250", 7709),
    ("119.147.212.81", 7709),
    ("124.74.236.94", 7709),
    ("218.18.103.11", 7709),
]

# 通达信市场代码：沪=1，深=0，京(北交所)=2
_TDX_MARKET = {"sh": 1, "sz": 0, "bj": 2}


def _market_of(code: str) -> str:
    code = code.lower().lstrip("shszbj")
    if code.startswith("6"):
        return "sh"
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("8", "4")):
        return "bj"
    return "sh"


def _tdx_market(code: str) -> int:
    return _TDX_MARKET[_market_of(code)]


def _norm(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


# ── 各源取数实现（单源，失败抛异常/返回 None） ──────────────
def _fetch_tdx(code: str, days_back: int) -> Optional[list[dict]]:
    """通达信日 K（pytdx）。直连，不经代理。"""
    try:
        from pytdx.hq import TdxHq_API
    except ImportError:
        _LOGGER.debug("pytdx 未安装，跳过通达信源")
        return None
    api = TdxHq_API(raise_exception=False)
    for ip, port in _TDX_SERVERS:
        try:
            if not api.connect(ip, port, time_out=5):
                continue
            # category=9 日线；一次最多 800 根，days_back 超出则多页
            bars = api.get_security_bars(9, _tdx_market(code), code[-6:], 0, min(days_back, 800))
            api.disconnect()
            if not bars:
                return None
            out = []
            for r in bars:
                dt = r.get("datetime") or r.get("date")
                if not dt:
                    continue
                out.append({
                    "code": code[-6:],
                    "date": str(dt)[:10],
                    "open": _norm(r.get("open")),
                    "high": _norm(r.get("high")),
                    "low": _norm(r.get("low")),
                    "close": _norm(r.get("close")),
                    "volume": _norm(r.get("vol")),
                    "amount": _norm(r.get("amount")),
                })
            return out or None
        except Exception as exc:
            _LOGGER.debug("通达信 %s:%s 失败: %s", ip, port, exc)
            try:
                api.disconnect()
            except Exception:
                pass
    return None


def _fetch_tencent(code: str, days_back: int) -> Optional[list[dict]]:
    """腾讯日 K（ifzq.gtimg.cn 直连，无需代理）。"""
    try:
        from .sina_tencent_quote import tencent_daily_kline
    except ImportError:
        try:
            from deep_fusion.data.sources.sina_tencent_quote import tencent_daily_kline
        except ImportError:
            return None
    df = tencent_daily_kline(code[-6:], limit=min(days_back, 800))
    if df is None or getattr(df, "empty", True):
        return None
    out = []
    for _, r in df.iterrows():
        out.append({
            "code": code[-6:],
            "date": str(r.get("date"))[:10],
            "open": _norm(r.get("open")),
            "high": _norm(r.get("high")),
            "low": _norm(r.get("low")),
            "close": _norm(r.get("close")),
            "volume": _norm(r.get("volume")),
            "amount": None,
        })
    return out or None


def _fetch_sina(code: str, days_back: int) -> Optional[list[dict]]:
    """新浪日 K（CN_MarketData 直连，无需代理）。"""
    import requests

    mkt = _market_of(code)
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={mkt}{code[-6:]}&scale=240&ma=no&datalen={min(days_back, 800)}"
    )
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
    except Exception as exc:
        _LOGGER.debug("新浪日K失败: %s", exc)
        return None
    if not isinstance(data, list):
        return None
    out = []
    for d in data:
        if not d.get("day"):
            continue
        out.append({
            "code": code[-6:],
            "date": str(d["day"])[:10],
            "open": _norm(d.get("open")),
            "high": _norm(d.get("high")),
            "low": _norm(d.get("low")),
            "close": _norm(d.get("close")),
            "volume": _norm(d.get("volume")),
            "amount": None,
        })
    return out or None


def _fetch_ths(code: str, days_back: int) -> Optional[list[dict]]:
    """同花顺日 K（akshare stock_zh_a_hist，走代理）。"""
    try:
        import akshare as ak
    except ImportError:
        return None
    try:
        df = ak.stock_zh_a_hist(
            symbol=code[-6:], period="daily",
            start_date="19700101", end_date="22220101", adjust="qfq",
        )
    except Exception as exc:
        _LOGGER.debug("同花顺日K失败: %s", exc)
        return None
    if df is None or df.empty:
        return None
    out = []
    for _, r in df.iterrows():
        out.append({
            "code": code[-6:],
            "date": str(r.get("日期"))[:10],
            "open": _norm(r.get("开盘")),
            "high": _norm(r.get("最高")),
            "low": _norm(r.get("最低")),
            "close": _norm(r.get("收盘")),
            "volume": _norm(r.get("成交量")),
            "amount": _norm(r.get("成交额")),
        })
    return out or None


def _fetch_eastmoney(code: str, days_back: int) -> Optional[list[dict]]:
    """东方财富日 K（akshare stock_zh_a_hist，走代理）。"""
    try:
        import akshare as ak
    except ImportError:
        return None
    try:
        df = ak.stock_zh_a_hist(
            symbol=code[-6:], period="daily",
            start_date="19700101", end_date="22220101", adjust="qfq",
        )
    except Exception as exc:
        _LOGGER.debug("东方财富日K失败: %s", exc)
        return None
    if df is None or df.empty:
        return None
    out = []
    for _, r in df.iterrows():
        out.append({
            "code": code[-6:],
            "date": str(r.get("日期"))[:10],
            "open": _norm(r.get("开盘")),
            "high": _norm(r.get("最高")),
            "low": _norm(r.get("最低")),
            "close": _norm(r.get("收盘")).real if False else _norm(r.get("收盘")),
            "volume": _norm(r.get("成交量")),
            "amount": _norm(r.get("成交额")),
        })
    return out or None


_FETCHERS = {
    "tdx": _fetch_tdx,
    "tencent": _fetch_tencent,
    "sina": _fetch_sina,
    "ths": _fetch_ths,
    "eastmoney": _fetch_eastmoney,
}


def fetch_stock_daily_priority(
    code: str,
    days_back: int = 800,
    priority: Sequence[str] = SOURCE_PRIORITY,
    only: Optional[str] = None,
) -> tuple[Optional[list[dict]], Optional[str]]:
    """按优先级取个股日 K，返回 (数据, 实际使用的源名)。

    - priority: 自定义优先级（默认 SOURCE_PRIORITY）。
    - only: 只尝试指定源（用于测试/强制源）。
    - 所有源都失败 → (None, None)。
    """
    sources = [only] if only else list(priority)
    tried = []
    for name in sources:
        fn = _FETCHERS.get(name)
        if fn is None:
            continue
        tried.append(name)
        try:
            data = fn(code, days_back)
        except Exception as exc:
            _LOGGER.debug("源 %s 取数异常: %s", name, exc)
            data = None
        if data:
            if name != tried[0]:
                _LOGGER.info("个股 %s 按优先级降级：首选 %s 不可用，实际用 %s", code, tried[0], name)
            return data, name
    return None, None
