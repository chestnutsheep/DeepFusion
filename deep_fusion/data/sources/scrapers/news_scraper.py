#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新浪财经滚动新闻 / 关键词检索轻量封装。

来源：实测 2026-08-05，东方财富 news 接口（np-listapi / search-api）全部 404 失效，
财联社官方 API 需动态 sign 不可用。改用新浪财经官方滚动新闻接口（直连，无需代理）：

    https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&num=N&page=P&k=<关键词>

返回 JSON：result.data[] 每条含 title / intro（摘要）/ url / ctime（Unix 秒）/ media_name。
支持关键词检索（k 参数），可作为政策/事件驱动选股的关键词检索与实时快讯补充源。

注意：该接口直连（腾讯/新浪源不受代理开关影响），失败时返回空列表，不阻塞主流程。
"""
from datetime import datetime
from urllib.parse import urlencode
from typing import List, Dict, Optional

from .http_utils import http_get_json

# 新浪财经滚动新闻接口（pageid=153&lid=2509 为"财经要闻/7x24"频道，实测可用）
_SINA_ROLL = "https://feed.mix.sina.com.cn/api/roll/get"


def _parse_sina_item(item: Dict) -> Optional[Dict]:
    """解析单条新浪滚动新闻为统一结构。"""
    try:
        title = (item.get("title") or "").strip()
        if not title:
            return None
        ctime = item.get("ctime") or item.get("ctime2") or 0
        try:
            ctime = int(ctime)
        except (TypeError, ValueError):
            ctime = 0
        if ctime > 0:
            pub = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
        else:
            pub = ""
        intro = (item.get("intro") or "").strip()
        # intro 有时是"来源：xxx"，作为摘要价值低，优先用 wap_content / summary
        summary = item.get("wap_content") or item.get("summary") or intro
        return {
            "title": title,
            "url": item.get("url", "") or item.get("wapurl", ""),
            "publish_time": pub,
            "source": item.get("media_name", "") or "",
            "summary": summary,
            "stock_codes": item.get("stock_codes") or [],
            "keywords": [],
        }
    except Exception:
        return None


def fetch_sina_roll(num: int = 30, page: int = 1, keyword: str = "") -> List[Dict]:
    """新浪财经滚动新闻（7x24 实时快讯补充源）。

    Args:
        num: 每页条数（默认 30）
        page: 页码（从 1 起）
        keyword: 可选关键词过滤（空=全量财经要闻）
    Returns:
        标准化 dict 列表（title/url/publish_time/source/summary）
    """
    params = {
        "pageid": "153",
        "lid": "2509",
        "num": num,
        "page": page,
        "k": keyword,
    }
    url = f"{_SINA_ROLL}?{urlencode(params)}"
    data = http_get_json(url)
    if not data:
        return []
    items = (data.get("result") or {}).get("data") or []
    out = []
    for it in items:
        art = _parse_sina_item(it)
        if art:
            out.append(art)
    return out


def fetch_market_news(page: int = 1, page_size: int = 30) -> List[Dict]:
    """新浪财经市场快讯（替代失效的东财 category_stock）。直连无需代理。"""
    return fetch_sina_roll(num=page_size, page=page)


def search_news(keyword: str, page: int = 1, page_size: int = 20) -> List[Dict]:
    """按关键词检索新浪财经文章。直连无需代理。"""
    if not keyword:
        return []
    return fetch_sina_roll(num=page_size, page=page, keyword=keyword)


if __name__ == "__main__":
    import json as _j
    print("== sina roll (latest) ==")
    print(_j.dumps(fetch_market_news(1, 5), ensure_ascii=False, indent=2))
    print("== search 半导体 ==")
    print(_j.dumps(search_news("半导体", 1, 5), ensure_ascii=False, indent=2))
