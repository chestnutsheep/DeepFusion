#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地数据采集工具汇总包（scrapers）。

把多个第三方 skill 的"可用工具部分"复制到本地，避免每次翻多份文件。
来源：
  - cnfinancialscraper（全能金融爬虫 v4.7.1）：regulatory_scraper / cls_scraper / news_scraper / http_utils
  - hot（热点数据采集）：hot/*.js（Node 脚本，市场情绪/舆情热度补充源）

设计（遵循 superdesign "设计优先"：先定接口再实现）：
  本包只暴露干净的聚合入口，各渠道内部实现互不污染，且复用 DeepFusion 既有的
  PolicyDB / _extract_detail 框架（见 data/sources/policy.py）。

对外 API：
  - collect_realtime(max_items=...) -> list[dict]   实时政策/快讯（监管 + 财联社7x24 + 新浪滚动）
  - collect_regulatory(...)                          监管三机构（证监会/央行/金监总局）
  - collect_cls(...)                                 财联社 7x24 电报
  - search_news(keyword)                             新浪关键词检索（直连，无需代理）
  - run_hot(platform='all') -> dict                 调用 Node 热点脚本（行情外情绪源）

注意：监管接口需经代理（clash-verge 全局接管 127.0.0.1:7897）；新浪/财联社/腾讯源走直连，
不受代理开关影响，始终可作兜底。东财 news 接口（np-listapi / search-api）经实测 2026-08-05
全部 404 失效，已由新浪接口替代。
"""
from .http_utils import http_get, http_get_json, parse_html
from .regulatory_scraper import fetch_csrc, fetch_pbc, fetch_nfra, fetch_all as fetch_regulatory_all
from .cls_scraper import fetch_cls_telegraph
from .news_scraper import fetch_market_news, search_news, fetch_sina_roll


def collect_regulatory(max_items: int = 15) -> list:
    """监管三机构（证监会/央行/金监总局）最新政策。"""
    try:
        return fetch_regulatory_all(max_items=max_items)
    except Exception as e:
        print(f"[scrapers] collect_regulatory 失败: {e}")
        return []


def collect_cls(num: int = 50) -> list:
    """财联社 7x24 电报（实时政策/快讯，直连无需代理）。"""
    try:
        return fetch_cls_telegraph(num=num)
    except Exception as e:
        print(f"[scrapers] collect_cls 失败: {e}")
        return []


def collect_realtime(max_items: int = 15, cls_num: int = 50) -> list:
    """汇总实时政策/快讯渠道：监管三机构 + 财联社 7x24。

    返回统一结构 list[dict]，每条含：date/time、title、url、org/source、summary。
    该入口供 build_noonnews.py 使用，作为"当日政策/讲话/会议"驱动选股的主源。
    """
    out = []
    for it in collect_regulatory(max_items=max_items):
        out.append({
            "date": it.get("date", ""),
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "org": it.get("org", ""),
            "summary": it.get("summary", ""),
        })
    for it in collect_cls(num=cls_num):
        content = it.get("content", "")
        out.append({
            "date": it.get("time", ""),
            "title": content,
            "url": it.get("url", ""),
            "org": "财联社" + (f"·{it['tag']}" if it.get("tag") else ""),
            # 7x24 快讯正文即标题内容，直接作为 body（fetch_policy_realtime 取 summary 落库）
            "summary": content,
        })
    # 新浪财经滚动新闻（直连，作为 7x24 实时快讯补充源）
    try:
        for it in fetch_sina_roll(num=max(20, cls_num // 2)):
            out.append({
                "date": it.get("publish_time", ""),
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "org": "新浪财经" + (f"·{it['source']}" if it.get("source") else ""),
                "summary": it.get("summary", ""),
            })
    except Exception as e:
        print(f"[scrapers] collect_sina_roll 失败: {e}")
    return out


def search_news_cn(keyword: str, page: int = 1, page_size: int = 20) -> list:
    """东财关键词新闻检索（需代理）。"""
    try:
        return search_news(keyword, page=page, page_size=page_size)
    except Exception as e:
        print(f"[scrapers] search_news_cn 失败: {e}")
        return []


def run_hot(platform: str = "all") -> dict:
    """调用本地 Node 热点脚本（hot/crawl-hot.js），行情外市场情绪/舆情热度源。

    Args:
        platform: all | douyin | weibo | baidu | bilibili | kuaishou
    Returns:
        dict（脚本 stdout 的 JSON）；失败返回 {"status": "error", ...}
    """
    import subprocess, os, sys, json
    script = os.path.join(os.path.dirname(__file__), "hot", "crawl-hot.js")
    if not os.path.exists(script):
        return {"status": "error", "message": "crawl-hot.js 不存在"}
    try:
        proc = subprocess.run(
            [sys.executable.replace("python", "node") or "node", script, f"--platform={platform}"],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {"status": "error", "message": proc.stderr.strip() or "node 执行失败"}
        return json.loads(proc.stdout)
    except FileNotFoundError:
        return {"status": "error", "message": "node 未安装"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


__all__ = [
    "http_get", "http_get_json", "parse_html",
    "fetch_csrc", "fetch_pbc", "fetch_nfra", "fetch_regulatory_all",
    "fetch_cls_telegraph", "fetch_market_news", "search_news", "fetch_sina_roll",
    "collect_regulatory", "collect_cls", "collect_realtime", "search_news_cn", "run_hot",
]


if __name__ == "__main__":
    import json
    print("== 实时政策/快讯汇总 ==")
    print(json.dumps(collect_realtime(max_items=5, cls_num=10), ensure_ascii=False, indent=2))
