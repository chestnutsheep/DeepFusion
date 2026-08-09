#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实时 7x24 快讯爬虫（新浪直连兜底，无需代理）。

来源：cnfinancialscraper skill 的 cls_scraper 思路 + 实测可靠的直连源。
财联社官方 API 需动态 sign，直连返回 errno:50101，不可用；
改用**新浪 7x24 全球快讯**（akshare stock_info_global_sina 同款接口，直连 5s 内可用），
作为"当日政策/讲话/会议"最实时的兜底快讯源。返回标准化 dict 列表：
    {time, content, url, tag}

用法：from .cls_scraper import fetch_cls_telegraph
"""
import json
import re
from datetime import datetime

from .http_utils import http_get

# 新浪 7x24 快讯接口（直连，无需代理）
# ⚠️ 实测 2026-08-05：该接口返回 404 已失效，仅作历史保留，不再作为可用源。
_SINA_API = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_51toutiao?type=0&page_size={num}&page_index={page}"
# 财联社（需签名，保留作首选尝试，失败自动降级新浪）
# ⚠️ 实测返回 errno:50101（需动态 sign），不可用；主路径已切到 akshare stock_info_global_sina 直连。
_CLS_API = "https://www.cls.cn/nodeapi/telegraphList?app=CailianpressWeb&os=web&sv=8.4.6&rn={num}&order=1"


def _parse_sina(num, page):
    """新浪 7x24 快讯（东方财富新闻 api，直连）。"""
    url = _SINA_API.format(num=num, page=page)
    text = http_get(url)
    if not text:
        return None
    m = re.search(r"\((.*)\)", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except Exception:
        return None
    out = []
    for it in data.get("data", {}).get("list", []):
        # 时间字段为毫秒时间戳
        ts = it.get("time") or it.get("showtime") or 0
        try:
            dt = datetime.fromtimestamp(int(ts) / 1000) if ts else None
        except Exception:
            dt = None
        out.append({
            "time": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
            "content": it.get("content") or it.get("title") or "",
            "url": it.get("url", "") or "",
            "tag": it.get("tag", "") or "",
        })
    return out


def _parse_cls(num, page):
    """财联社 7x24（尝试，需签名可能失败）。"""
    url = _CLS_API.format(num=num, page=page)
    text = http_get(url)
    if not text or "errno" in text:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    if data.get("errno") not in (0, None):
        return None
    items = data.get("data", {}).get("list") or data.get("data", {}).get("roll_data") or []
    out = []
    for it in items:
        ts = it.get("created_at") or it.get("time") or 0
        try:
            dt = datetime.fromtimestamp(int(ts)) if ts else None
        except Exception:
            dt = None
        out.append({
            "time": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
            "content": it.get("content") or it.get("title") or "",
            "url": "https://www.cls.cn/detail/" + str(it.get("id", "")) if it.get("id") else "",
            "tag": it.get("tag_name") or it.get("tag") or "",
        })
    return out


def _parse_akshare(num):
    """优先用 akshare 已验证可用的新浪 7x24（直连，无需代理）。"""
    try:
        import akshare as ak
        df = ak.stock_info_global_sina()
        out = []
        for _, row in df.iterrows():
            out.append({
                "time": str(row.get("时间", "")),
                "content": str(row.get("内容", "")),
                "url": "",
                "tag": "",
            })
            if len(out) >= num:
                break
        return out
    except Exception as e:
        print(f"[cls_scraper] akshare 新浪7x24 失败: {e}")
        return None


def fetch_cls_telegraph(num=50, page=0):
    """抓实时 7x24 快讯：优先 akshare 新浪直连，失败降级手动接口。

    Args:
        num: 条数（默认 50）
        page: 页码（0 起）
    Returns:
        list[{time, content, url, tag}]
    """
    # 首选 akshare 新浪 7x24（直连已验证）
    res = _parse_akshare(num)
    if res:
        return res
    # 降级财联社
    res = _parse_cls(num, page)
    if res:
        return res
    # 降级新浪手动接口
    res = _parse_sina(num, page)
    if res:
        return res
    print("[cls_scraper] 全部源失败")
    return []


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(fetch_cls_telegraph(20), ensure_ascii=False, indent=2))
