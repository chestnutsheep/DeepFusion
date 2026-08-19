#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新华网政策/时政频道吹风信号采集。

定位：补齐"十五五/会议强调/规划印发"类重要政策信号缺口。
用户每天在各券商平台看到的"一会儿一个十五五文件、开会强调 xxxx 发展"，
这类官方吹风/规划发布主源在新华网（news.cn）时政频道，原采集调度未覆盖。

实测（2026-08-19）：https://www.news.cn/politics/ 直连可抓（len>36k），
按关键词过滤可稳定命中"十五五"专题（如《民用航空发展十五五规划》印发、
多部门联合印发《生态保护十五五规划》等）。gov.cn 为 JS 渲染纯 HTTP 抓不到，
新华网作官方吹风首选源。

返回统一结构 list[dict]：{date, title, url, org, org_code, summary}
注意：新华网列表页多为专题/通稿，无精确日期时 date 留空，由上层按其他信号判断。
"""
import re
from datetime import date, timedelta

from .http_utils import http_get, urljoin, parse_html

# 新华网时政/政策频道（实测可用，直连无需代理）
_XINHUA_POLITICS = "https://www.news.cn/politics/"

# 重要政策信号关键词：命中即视为"规划/会议/吹风"类高价值政策
_SIGNAL_KEYWORDS = [
    "十五五", "规划", "政治局", "国常会", "国务院", "发改委", "中办", "国办",
    "会议强调", "中央经济工作会议", "印发", "实施方案", "若干意见", "行动计划",
    "部署", "主席", "总书记", "政府工作报告", "金融工作会议",
]

# 导航噪音词（过滤栏目/页脚链接）
_NAV_NOISE = {
    "首页", "客户端", "新华网", "微门户", "登录", "注册", "网站地图", "联系我们",
    "版权", "法律声明", "隐私政策", "无障碍", "纠错", "English", "更多", "图集",
    "专题", "视频", "直播", "评论", "快讯", "图片", "英文", "地方", "财经", "国际",
}

# 只保留最近 N 天内有明确日期的条目；无日期的吹风信号保留（交由上层）
_MAX_AGE_DAYS = int(__import__("os").getenv("XINHUA_MAX_AGE_DAYS", "30"))


def _is_fresh(date_str: str) -> bool:
    """有明确日期则过滤窗口外旧帖；无日期保留。"""
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
    """从新华网政策频道 HTML 抽取命中信号的 (title, url, date_str)。"""
    soup = parse_html(html)
    if not soup:
        return []
    out = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        low = title.lower()
        if low in _NAV_NOISE or any(n in title for n in ("【", "】", ">>", " More")):
            continue
        # 仅保留命中重要政策信号关键词的条目
        if not any(k in title for k in _SIGNAL_KEYWORDS):
            continue
        href = a["href"].strip()
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://www.news.cn" + href
        elif not href.startswith("http"):
            continue
        # 同 a 标签附近 120 字符内找日期
        tail = str(a)[:200]
        dm = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", tail)
        date_str = dm.group(0) if dm else ""
        out.append({"title": title, "url": href, "date": date_str})
    # 去重（同 url）
    seen, uniq = set(), []
    for it in out:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    return uniq


def fetch_xinhua(max_items: int = 25) -> list:
    """新华网政策吹风信号：十五五/规划/会议/印发类高价值政策。

    Returns:
        标准化 dict 列表 [{date, title, url, org, org_code, summary}]
    """
    html = http_get(_XINHUA_POLITICS, timeout=15)
    if not html:
        return []
    rows = _parse(html)
    out = []
    for r in rows[:max_items]:
        item = {
            "date": r["date"],
            "title": r["title"],
            "url": r["url"],
            "org": "新华网",
            "org_code": "xinhua",
            "summary": "",
        }
        if _is_fresh(item["date"]):
            out.append(item)
    return out


if __name__ == "__main__":
    import json
    data = fetch_xinhua()
    print(json.dumps(data, ensure_ascii=False, indent=2))
