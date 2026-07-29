"""实时行情工具（腾讯 gtimg 直连，不受 clash 代理开关影响）。

提供两类能力：
- market_open_now(): 判断当前是否为 A股交易时段（用于决定"实时 vs 最近交易日收盘"）。
- tencent_realtime(codes): 批量取个股实时快照（最新价/涨跌幅/换手/PE/PB）。

gtimg 字段顺序（按 ~ 拆分，0 基）：
  1=名称, 2=代码, 3=最新价, 4=昨收, 5=今开, 31=涨跌额, 32=涨跌幅%, 33=换手%, 34=市盈率TTM, 35=市净率
"""
from __future__ import annotations

import time
from datetime import datetime

import requests

_GTIMG_URL = "https://qt.gtimg.cn/q="
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
_TIMEOUT = 8


def _prefix(code: str) -> str:
    code = code.strip()
    if code[:2] in ("sh", "sz", "bj"):
        return code
    if code[0] == "6":
        return "sh" + code
    if code[0] in ("0", "3"):
        return "sz" + code
    if code[0] in ("4", "8"):
        return "bj" + code
    return "sh" + code


def market_open_now(dt: datetime | None = None) -> bool:
    """当前是否处于 A股交易时段（周一~周五 9:30-11:30 / 13:00-15:00）。"""
    dt = dt or datetime.now()
    if dt.weekday() >= 5:
        return False
    t = dt.time()
    return (
        (t >= __import__("datetime").time(9, 30) and t <= __import__("datetime").time(11, 30))
        or (t >= __import__("datetime").time(13, 0) and t <= __import__("datetime").time(15, 0))
    )


def tencent_realtime(codes: list[str]) -> dict[str, dict]:
    """批量取实时快照，返回 {原始code: {name,price,change_pct,turnover,pe,pb}}。

    非交易时段 gtimg 返回最近交易日收盘数据（已满足"收盘用最近交易日"要求）。
    单只股票请求失败时该 code 缺省返回空 dict。
    """
    if not codes:
        return {}
    prefixed = [_prefix(c) for c in codes]
    url = _GTIMG_URL + ",".join(prefixed)
    out: dict[str, dict] = {}
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.encoding = "gbk"
        for line in resp.text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # key: v_sh600519
            raw = key[2:] if key.startswith("v_") else key
            val = val.strip().strip('"')
            if not val:
                continue
            f = val.split("~")
            if len(f) < 36:
                continue
            out[raw] = {
                "name": f[1],
                "price": _num(f[3]),
                "prev_close": _num(f[4]),
                "change_pct": _num(f[32]),
                "turnover": _num(f[33]),
                "pe": _num(f[34]),
                "pb": _num(f[35]),
            }
    except Exception:
        # 网络失败 → 返回已成功解析的部分（上游决定降级）
        pass
    return out


def _num(s: str):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def as_of_label() -> str:
    """数据时间戳标签：实时 or 最近交易日收盘。"""
    return "盘中实时" if market_open_now() else "最近交易日收盘"
