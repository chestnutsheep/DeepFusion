#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""券商中国（stcn.com）吹风信号采集。

定位：补齐"券商平台每日吹风"缺口。用户每天看各券商平台的最新消息，
券商中国（证券时报旗下）是卖方/媒体吹风的权威入口，覆盖"十五五/规划/会议/资本市场"
类政策解读与行业催化。原采集调度未覆盖。

实测（2026-08-19）：https://www.stcn.com/ 直连可抓（len>157k），
首页 /article/detail/ 链接结构稳定，按政策信号关键词过滤命中率高。

返回统一结构 list[dict]：{date, title, url, org, org_code, summary}
"""
import re
from datetime import date, timedelta

from .http_utils import http_get, urljoin, parse_html

_STCN_HOME = "https://www.stcn.com/"

# 高价值政策/吹风信号关键词（券商视角：规划/会议/政策/资本市场导向）
_SIGNAL_KEYWORDS = [
    "十五五", "规划", "政治局", "国常会", "国务院", "发改委", "中办", "国办",
    "会议强调", "中央经济工作会议", "印发", "实施方案", "若干意见", "行动计划",
    "部署", "政府工作报告", "金融工作会议", "资本市场", "政策", "改革", "利好",
    "金融工具", "专项", "扶持", "补贴", "退税", "降准", "降息", "稳增长",
]

# 噪音：公告/个股PDF/导航
_NAV_NOISE = {
    "首页", "客户端", "公众号", "电子报", "网页版", "移动版", "更多", "登录",
    "注册", "关于我们", "联系我们", "版权", "法律声明", "隐私政策", "友情链接",
}
# 过滤纯个股公告类（xp.stcn.com PDF / 董事会决议）
_NOISE_URL_PREFIX = ("xp.stcn.com", "pdf", "board", "公告")

_MAX_AGE_DAYS = int(__import__("os").getenv("STCN_MAX_AGE_DAYS", "7"))


def _is_fresh(date_str: str) -> bool:
    if not date_str:
        return True
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", date_str)
    if not m:
        return True
    try:
        pub = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return True
    return pub >= (date.today() - timedelta(days=_MAX_AGE_DAYS))


def _parse(html: str) -> list:
    soup = parse_html(html)
    if not soup:
        return []
    out = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        low = title.lower()
        if low in _NAV_NOISE or any(n in title for n in ("【", "】", ">>")):
            continue
        if not any(k in title for k in _SIGNAL_KEYWORDS):
            continue
        href = a["href"].strip()
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://www.stcn.com" + href
        elif not href.startswith("http"):
            continue
        # 过滤纯个股公告 PDF
        if any(np in href for np in _NOISE_URL_PREFIX):
            continue
        # 标题里常带 "08-18 21:30" 日期，提取
        dm = re.search(r"(\d{2})-(\d{2})\s*\d{1,2}:\d{2}", title)
        date_str = ""
        if dm:
            y = date.today().year
            date_str = f"{y}-{dm.group(1)}-{dm.group(2)}"
            title = title.replace(dm.group(0), "").strip()
        out.append({"title": title, "url": href, "date": date_str})
    seen, uniq = set(), []
    for it in out:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    return uniq


def fetch_stcn(max_items: int = 25) -> list:
    """券商中国吹风信号：十五五/规划/会议/资本市场政策解读。"""
    html = http_get(_STCN_HOME, timeout=15)
    if not html:
        return []
    rows = _parse(html)
    out = []
    for r in rows[:max_items]:
        item = {
            "date": r["date"],
            "title": r["title"],
            "url": r["url"],
            "org": "券商中国",
            "org_code": "stcn",
            "summary": "",
        }
        if _is_fresh(item["date"]):
            out.append(item)
    return out


if __name__ == "__main__":
    import json
    data = fetch_stcn()
    print(json.dumps(data, ensure_ascii=False, indent=2))
