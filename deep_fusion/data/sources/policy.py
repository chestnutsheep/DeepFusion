"""Multi-site policy document tracker.

Sites: gov.cn / stats.gov.cn / pbc.gov.cn / mof.gov.cn / ndrc.gov.cn / safe.gov.cn
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable

import requests as _rq
from bs4 import BeautifulSoup

_SESSION = _rq.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
_SESSION.trust_env = False

from ...shared.policy_db import PolicyDB

db = PolicyDB()
_ORG_MAP: dict[str, str] = {}  # url_pattern → org_name, set in _sites

# ── 通用工具 ─────────────────────────────────────────

_DATE_RE = re.compile(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)")
_KW_SET = {"五年规划", "十五五", "十四五", "改革", "创新", "数字经济",
           "绿色", "碳中和", "新能源", "产业链", "消费", "投资",
           "房地产", "地方债", "专项债", "财政", "货币", "降准", "降息",
           "人工智能", "数据要素", "国企改革", "民营"}


def _extract_detail(entry: dict) -> dict:
    """补全单篇详情：标题/日期/机构/正文/关键词。"""
    try:
        r = _SESSION.get(entry["url"], timeout=15)
        if r.status_code != 200:
            return entry
        if r.encoding and r.encoding.lower() == "iso-8859-1" and r.apparent_encoding:
            r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        # 标题 — 多策略
        title = ""
        for sel in [["h1"], ["h2"], ["h3"], [".title", ".bt", ".news_title"], ["#title", "#bt"]]:
            for tag_or_cls in sel:
                if tag_or_cls.startswith(".") or tag_or_cls.startswith("#"):
                    el = soup.select_one(tag_or_cls)
                else:
                    el = soup.find(tag_or_cls)
                if el:
                    t = el.get_text(strip=True)
                    if len(t) > 5:
                        title = t
                        break
            if title:
                break
        # <title> 标签兜底
        if not title and soup.title and soup.title.string:
            t = soup.title.string.strip()
            # 去掉站点后缀
            for s in ["_国务院政策文件库", "中国政府网", "_财政部", "国家统计局"]:
                t = t.replace(s, "")
            if len(t) > 5:
                title = t
        # meta 兜底
        if not title:
            og = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
            if og and og.get("content"):
                title = og["content"]
        # 只有找到的标题明显比列表标题好时才覆盖
        # （列表标题可能短/不完整，但比"索引号"好）
        if title and len(title) > len(entry.get("title", "")) and "索引" not in title and "微信" not in title:
            entry["title"] = title
        if not entry.get("title"):
            entry["title"] = "(标题提取失败)"

        # 日期
        for el in soup.find_all(["span", "time", "p", "div"]):
            m = _DATE_RE.search(el.get_text(strip=True))
            if m:
                entry["publish_date"] = m.group(1)
                break

        # 机构 — 从 URL 推断比正文可靠
        if not entry.get("organization"):
            for pattern, org_name in _ORG_MAP.items():
                if re.search(pattern, entry["url"]):
                    entry["organization"] = org_name
                    break

        # 正文
        body_parts = []
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 20:
                body_parts.append(txt)
        entry["body"] = "\n".join(body_parts[:150])
        body_text = " ".join(body_parts)

        found = [kw for kw in _KW_SET if kw in body_text]
        entry["keywords"] = ",".join(found)

    except Exception as e:
        print(f"  ⚠ 详情失败: {entry.get('url', '?')}: {e}")
    return entry


def _parse_list(url: str, link_filter: Callable[[str], bool],
                source: str, org: str = "", max_pages: int = 2) -> list[dict]:
    """通用列表页解析。"""
    results: list[dict] = []
    seen: set[str] = set()
    base_domain = re.match(r"(https?://[^/]+)", url).group(1)

    for page in range(1, max_pages + 1):
        page_url = f"{url}index.htm" if page == 1 else re.sub(r"index.*\.htm", f"index_{page}.htm", url)
        try:
            r = _SESSION.get(page_url, timeout=15)
            if r.status_code != 200:
                continue
            if r.encoding and r.encoding.lower() == "iso-8859-1" and r.apparent_encoding:
                r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                txt = a.get_text(strip=True)
                if not txt or len(txt) < 8:
                    continue
                full = href if href.startswith("http") else f"{base_domain}{href}"
                if not link_filter(full):
                    continue
                if full in seen:
                    continue
                seen.add(full)
                results.append({
                    "title": txt,
                    "url": full,
                    "source": source,
                    "organization": org,
                    "publish_date": "",
                    "found_at": datetime.now().isoformat(),
                    "body": "",
                    "keywords": "",
                })
        except Exception as e:
            print(f"  ⚠ {page_url}: {e}")
    return results


# ── 各站抓取 ─────────────────────────────────────────

def fetch_gov(max_pages: int = 2) -> list[dict]:
    """国务院政策文件库 (gov.cn/zhengce/content/)。"""
    _ORG_MAP["gov.cn"] = "国务院"
    return _parse_list(
        "https://www.gov.cn/zhengce/",
        lambda u: bool(re.search(r"/zhengce/content/\d+", u)) and "home" not in u,
        source="国务院政策文件库", org="国务院", max_pages=max_pages,
    )


def fetch_stats(max_pages: int = 2) -> list[dict]:
    """国家统计局 (stats.gov.cn/sj/zxfb/ + tjgb/)。"""
    _ORG_MAP["stats.gov.cn"] = "国家统计局"
    results = []
    for section in ["sj/zxfb/", "sj/tjgb/"]:
        results.extend(_parse_list(
            f"https://www.stats.gov.cn/{section}",
            lambda u: bool(re.search(r"/20\d{4}/t\d+", u)),
            source=f"统计局-{'最新发布' if 'zxfb' in section else '公报'}",
            org="国家统计局", max_pages=max_pages,
        ))
    return results


def fetch_pbc(max_pages: int = 2) -> list[dict]:
    """央行 (pbc.gov.cn) — 货币政策执行报告 / 金融稳定 / 人民币国际化。"""
    _ORG_MAP["pbc.gov.cn"] = "中国人民银行"
    results = []
    sections = [
        ("https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/", "货币政策报告"),
        ("https://www.pbc.gov.cn/jinrongwendingju/146766/", "金融稳定"),
        ("https://www.pbc.gov.cn/huobijinrongju/125392/", "人民币国际化"),
    ]
    for sec_url, sec_name in sections:
        results.extend(_parse_list(
            sec_url,
            lambda u: bool(re.search(r"/20\d{4}/", u)) and "index" not in u,
            source=f"央行-{sec_name}", org="中国人民银行", max_pages=max_pages,
        ))
    return results


def fetch_mof(max_pages: int = 2) -> list[dict]:
    """财政部 (mof.gov.cn) — 预算 / 财政数据。"""
    _ORG_MAP["mof.gov.cn"] = "财政部"
    results = []
    sections = [
        ("https://www.mof.gov.cn/zhengwuxinxi/caizhengshuju/", "财政数据"),
        ("https://www.mof.gov.cn/zhengwuxinxi/caizhengxinxi/", "财政信息"),
    ]
    for sec_url, sec_name in sections:
        results.extend(_parse_list(
            sec_url,
            lambda u: "mof.gov.cn" in u and bool(re.search(r"/20\d{4}/", u)),
            source=f"财政部-{sec_name}", org="财政部", max_pages=max_pages,
        ))
    return results


def fetch_ndrc(max_pages: int = 2) -> list[dict]:
    """发改委 (ndrc.gov.cn)。"""
    _ORG_MAP["ndrc.gov.cn"] = "国家发改委"
    return _parse_list(
        "https://www.ndrc.gov.cn/fzgggz/",
        lambda u: "ndrc.gov.cn" in u and bool(re.search(r"/20\d{4}/", u)),
        source="发改委规划", org="国家发改委", max_pages=max_pages,
    )


def fetch_safe(max_pages: int = 2) -> list[dict]:
    """外管局 (safe.gov.cn)。"""
    _ORG_MAP["safe.gov.cn"] = "国家外汇管理局"
    return _parse_list(
        "https://www.safe.gov.cn/safe/whhl/index.html",
        lambda u: "safe.gov.cn" in u and bool(re.search(r"/20\d{4}/", u)),
        source="外管局", org="国家外汇管理局", max_pages=max_pages,
    )


# ── 统一调度 ─────────────────────────────────────────

_FETCHERS: list[tuple[str, Callable]] = [
    ("国务院", fetch_gov),
    ("统计局", fetch_stats),
    ("央行", fetch_pbc),
    ("财政部", fetch_mof),
    ("发改委", fetch_ndrc),
    ("外管局", fetch_safe),
]


def collect_all(max_pages: int = 2) -> dict[str, dict[str, int]]:
    """全站采集。"""
    totals = {}
    for name, fn in _FETCHERS:
        print(f"\n── {name} ──")
        try:
            entries = fn(max_pages=max_pages)
            print(f"  找到 {len(entries)} 条")
            new = 0
            for e in entries:
                if db.exists(e["url"]):
                    continue
                e = _extract_detail(e)
                db.save(e)
                new += 1
            totals[name] = {"total": len(entries), "new": new}
            print(f"  新增 {new} 条")
        except Exception as ex:
            print(f"  ❌ {ex}")
            totals[name] = {"error": str(ex)}
    return totals


def collect(max_pages: int = 3) -> dict[str, int]:
    """兼容旧接口：仅爬国务院。"""
    entries = fetch_gov(max_pages)
    new = 0
    for e in entries:
        if db.exists(e["url"]):
            continue
        e = _extract_detail(e)
        db.save(e)
        new += 1
    return {"total": len(entries), "new": new}
