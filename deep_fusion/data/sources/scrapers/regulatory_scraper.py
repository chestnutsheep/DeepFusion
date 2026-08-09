#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监管政策爬虫：央行 / 证监会 / 金监总局。

来源：cnfinancialscraper skill（全能金融爬虫 v4.7.1），import 路径已适配本地 scrapers 包。
提供 fetch_csrc / fetch_pbc / fetch_nfra 三个独立函数，返回标准化 dict 列表：
    {date, title, url, org, org_code, summary}

注意：这些站点部分需经代理（clash-verge 全局接管），http_utils 已处理降级。
"""
import re
from datetime import datetime, date

from .http_utils import http_get, urljoin

# URL 已逐一实测可用（2026-08-05）。
# 注：国家金融监督管理总局官网为 JS 渲染，纯 HTTP 抓不到政策列表（verify 后 404/空），
# 暂不纳入硬抓取（避免噪音）；其政策可通过东财 search_news('金融监管') 经代理补充。
_ORGS = {
    "csrc": {
        "name": "中国证监会",
        "url": "http://www.csrc.gov.cn/csrc/c100039/common_list.shtml",
        "base": "http://www.csrc.gov.cn",
        "date_re": r"(\d{4}-\d{2}-\d{2})",
    },
    "pbc": {
        "name": "中国人民银行",
        "url": "http://www.pbc.gov.cn/zhengcehuobisi/125207/125217/index.html",
        "base": "http://www.pbc.gov.cn",
        "date_re": r"(\d{4}-\d{2}-\d{2})",
    },
}


# 明显是页面导航/无意义的词，过滤掉
_NAV_NOISE = {"english", "更多", "首页", "上一页", "下一页", "机构概况", "领导班子",
              "证监会介绍", "联系我们", "站点地图", "法律声明", "隐私保护", "网站纠错",
              "政务微信", "政务微博", "客户端", "留言", "关于我们", "设为首页"}

def _parse_list(html, org_conf, org_code):
    """从列表页 HTML 抽取 (title, url, date_str)。

    策略：扫描所有 a 标签，保留"文本长度>=6 且非导航词 且 附近含日期"的条目，
    避免抓到页面导航文字。
    """
    items = []
    if not html:
        return items
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.S | re.I)
    for m in pattern.finditer(html):
        href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        text = text.replace("&nbsp;", " ").strip()
        if not text or len(text) < 6:
            continue
        low = text.lower()
        if low in _NAV_NOISE or any(n in text for n in ("【更多】", ">>", " More")):
            continue
        # 在 a 标签附近 80 字符内找日期
        start = max(0, m.start() - 40)
        tail = html[start:m.end() + 80]
        dm = re.search(org_conf["date_re"], tail)
        date_str = dm.group(1) if dm else ""
        if not date_str:
            continue  # 政策列表必须有日期，否则多为导航/栏目
        full_url = urljoin(org_conf["base"], href) if not href.startswith("http") else href
        items.append({"title": text, "url": full_url, "date": date_str})
    # 去重（同 url）
    seen, uniq = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    return uniq


def _fetch_one(org_code, max_items=20):
    conf = _ORGS[org_code]
    html = http_get(conf["url"])
    rows = _parse_list(html, conf, org_code)
    out = []
    for r in rows[:max_items]:
        out.append({
            "date": r["date"],
            "title": r["title"],
            "url": r["url"],
            "org": conf["name"],
            "org_code": org_code,
            "summary": "",
        })
    return out


def fetch_csrc(max_items=20):
    """证监会政策/规则。"""
    return _fetch_one("csrc", max_items)


def fetch_pbc(max_items=20):
    """央行政策。"""
    return _fetch_one("pbc", max_items)


def fetch_nfra(max_items=20):
    """金监总局政策。"""
    return _fetch_one("nfra", max_items)


def fetch_all(max_items=15):
    """汇总三机构。"""
    out = []
    for code in _ORGS:
        try:
            out.extend(_fetch_one(code, max_items))
        except Exception as e:
            print(f"[regulatory_scraper] {code} 失败: {e}")
    return out


if __name__ == "__main__":
    import json
    data = fetch_all()
    print(json.dumps(data, ensure_ascii=False, indent=2))
