"""Policy tracking MCP tools — 国务院政策文件抓取与检索。"""
import json
import re
from collections import defaultdict
from datetime import datetime

from pydantic import Field

from ..data.sources import policy
from ..server import mcp

# ── 官方链接（机构名 → 官网，统一来源：shared/policy_orgs） ──
from ..shared.policy_orgs import ORG_OFFICIAL_URLS as _OFFICIAL_LINKS

# ── 月份名称 ──
_MONTH_NAMES = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


@mcp.tool(
    name="policy_collect",
    description="全站采集：国务院/统计局/央行/财政部/发改委/外管局 政策文件",
)
def policy_collect(max_pages: int = 2) -> str:
    results = policy.collect_all(max_pages=max_pages)
    lines = ["=== 政策采集报告 ==="]
    total_all = 0
    new_all = 0
    for site, r in results.items():
        if "error" in r:
            lines.append(f"  ❌ {site}: {r['error']}")
        else:
            lines.append(f"  ✅ {site}: {r['total']} 条, 新增 {r['new']}")
            total_all += r["total"]
            new_all += r["new"]
    lines.append(f"合计: {total_all} 条, 新增 {new_all}")
    return "\n".join(lines)


@mcp.tool(
    name="policy_search",
    description="搜索已入库的政策文件",
)
def policy_search(
        keyword: str = "",
        org: str = "",
        limit: int = 20,
        year: int | None = None,
        sector: str = "",
) -> str:
    from ..shared.policy_db import PolicyDB
    db = PolicyDB()
    results = db.search(keyword=keyword, org=org, limit=limit, year=year, sector=sector)
    if not results:
        return "无匹配结果"
    lines = [f"共 {len(results)} 条"]
    for r in results:
        kw = f" [{r['keywords']}]" if r.get("keywords") else ""
        sc = f" ⟨板块:{r['sector']}⟩" if r.get("sector") else ""
        org = f" ({r['organization']})" if r.get("organization") else ""
        sent = r.get("sentiment", "中性")
        sent_tag = f"〈{sent}〉" if sent and sent != "中性" else ""
        date = r.get("publish_date", "") or ""
        url = r.get("url", "") or ""
        lines.append(f"  {date:12s} {r['title'][:50]}{org}{sent_tag}{sc}{kw}  {url}")
    return "\n".join(lines)


@mcp.tool(
    name="policy_detail",
    description="查看某篇政策文件详情",
)
def policy_detail(
        url: str = Field(..., description="政策文件URL"),
) -> str:
    from ..shared.policy_db import PolicyDB
    db = PolicyDB()
    doc = db.get(url)
    if not doc:
        return json.dumps({"error": "未找到", "found": False}, ensure_ascii=False)
    body = doc.get("body", "")[:2000]
    out = {k: v for k, v in doc.items() if k != "raw_json"}
    out["found"] = True
    out["body"] = body  # 已截断至前2000字
    out["body_truncated"] = len(doc.get("body", "")) > 2000
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool(
    name="policy_stats",
    description="政策文件库统计",
)
def policy_stats() -> str:
    from ..shared.policy_db import PolicyDB
    db = PolicyDB()
    st = db.stats()
    lines = [f"政策文件库: 共 {st['total']} 篇"]
    for org, cnt in st.get("orgs", {}).items():
        lines.append(f"  {org}: {cnt} 篇")
    if st.get("last_collected"):
        lines.append(f"最后采集: {st['last_collected']}")
    return "\n".join(lines)


@mcp.tool(
    name="policy_timeline",
    description="获取某年政策时间线数据（按月聚合真实政策文件 + 长周期节点 + 官方链接），供前端渲染动态时间线",
)
def policy_timeline(year: int | None = None) -> str:
    """返回结构化 JSON，包含：
    - months: 每月政策事件列表（从已入库数据聚合）
    - long_cycle: 长周期战略节点
    - official_links: 官方直达链接
    - five_year_stage: 当前五年规划阶段
    """
    from ..shared.policy_db import PolicyDB
    db = PolicyDB()
    now_year = year or datetime.now().year

    # ── 按月聚合 ──
    monthly: dict[int, list[dict]] = defaultdict(list)
    results = db.search(limit=500, year=now_year, with_summary=True)
    for r in results:
        date_str = r.get("publish_date", "") or ""
        # 兼容 ISO 和中文日期格式提取月份
        m = re.match(r"(\d{4})[-/年](\d{1,2})", date_str)
        if m:
            month_idx = int(m.group(2)) - 1
            if 0 <= month_idx < 12:
                monthly[month_idx].append({
                    "title": (r.get("title") or "")[:60],
                    "org": r.get("organization", ""),
                    "date": date_str,
                    "keywords": (r.get("keywords") or "").split(",") if r.get("keywords") else [],
                    "sector": (r.get("sector") or "").split(",") if r.get("sector") else [],
                    "url": r.get("url", ""),
                })

    # ── 每月取代表性事件（按关键词丰富度排序，最多3条） ──
    months_data = []
    for mi in range(12):
        entries = monthly.get(mi, [])
        entries.sort(key=lambda e: len(e.get("keywords", [])), reverse=True)
        top = entries[:3]
        months_data.append({
            "month": _MONTH_NAMES[mi],
            "count": len(entries),
            "items": [
                {
                    "title": e["title"],
                    "org": e["org"],
                    "date": e["date"],
                    "keywords": e["keywords"][:5],
                    "sector": e.get("sector", [])[:5],
                    "url": e["url"],
                }
                for e in top
            ],
        })

    # ── 未来政策节点（统一从日历 Routine/政策会议种子读取，替代硬编码）──
    from ..reports import store
    upcoming = store.get_calendar_upcoming(400)  # 未来约13个月
    upcoming_schedule = [
        {"date": e["date"], "name": e["name"], "category": e["category"],
         "sentiment": e.get("sentiment", "中性"), "sector": e.get("sector", "")}
        for e in upcoming
        if e.get("category") in ("政策会议", "政策发布")
    ]
    # 长周期战略节点（规划/白皮书）从日历周期固定节点派生
    # 输出为前端期望结构：{year, label, is_major, date, category}
    long_cycle = []
    for s in upcoming_schedule:
        if "规划" in s["name"] or "白皮书" in s["name"]:
            ym = re.match(r"(\d{4})", s.get("date", "") or "")
            yr = int(ym.group(1)) if ym else now_year
            is_major = "规划" in s["name"]
            long_cycle.append({
                "year": yr,
                "label": s["name"],
                "is_major": is_major,
                "date": s.get("date", ""),
                "category": s.get("category", ""),
            })
    long_cycle.sort(key=lambda x: x["year"])

    # ── 最新政策（细节更多的时间线）──
    latest_sorted = sorted(
        results,
        key=lambda r: (r.get("publish_date", "") or ""),
        reverse=True,
    )
    latest = [
        {
            "title": (r.get("title") or "")[:80],
            "org": r.get("organization", ""),
            "dept": r.get("organization", ""),
            "date": r.get("publish_date", "") or "",
            "time": r.get("publish_date", "") or "",
            "keywords": (r.get("keywords") or "").split(",") if r.get("keywords") else [],
            "sector": (r.get("sector") or "").split(",") if r.get("sector") else [],
            "sentiment": r.get("sentiment", "中性"),
            "content": (r.get("content") or "").strip(),
            "url": r.get("url", ""),
        }
        for r in latest_sorted[:15]
    ]

    # ── 按板块(sector)分组叠放 ──
    from ..shared.policy_sectors import SECTOR_ORDER, sector_color
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        secs = (r.get("sector") or "").split(",") if r.get("sector") else []
        if not secs:
            secs = ["其他"]
        item = {
            "title": (r.get("title") or "")[:80],
            "org": r.get("organization", ""),
            "dept": r.get("organization", ""),
            "date": r.get("publish_date", "") or "",
            "time": r.get("publish_date", "") or "",
            "keywords": (r.get("keywords") or "").split(",") if r.get("keywords") else [],
            "sector": (r.get("sector") or "").split(",") if r.get("sector") else [],
            "sentiment": r.get("sentiment", "中性"),
            "content": (r.get("content") or "").strip(),
            "url": r.get("url", ""),
        }
        for s in secs:
            s = s.strip()
            if s:
                groups[s].append(item)
    sector_groups = [
        {
            "sector": s,
            "color": sector_color(s),
            "count": len(groups[s]),
            "items": sorted(groups[s], key=lambda x: (x["date"] or ""), reverse=True),
        }
        for s in SECTOR_ORDER
        if s in groups
    ]

    # ── 五年规划阶段 ──
    five_year_start = 2026
    five_year_end = 2030
    elapsed_years = max(0, now_year - five_year_start)
    total_years = five_year_end - five_year_start + 1
    stage = "开局起步期 · 夯实基础" if elapsed_years < 2 else \
        "攻坚深化期 · 重点突破" if elapsed_years < 3 else \
            "全面加速期 · 成果转化" if elapsed_years < 4 else \
                "收官决胜期 · 冲刺达标"

    result = {
        "year": now_year,
        "months": months_data,
        "latest": latest,
        "sector_groups": sector_groups,
        "long_cycle": long_cycle,
        "upcoming_schedule": upcoming_schedule,
        "official_links": [{"name": k, "url": v} for k, v in _OFFICIAL_LINKS.items()],
        "five_year": {
            "start": five_year_start,
            "end": five_year_end,
            "stage": stage,
        },
    }
    return json.dumps(result, ensure_ascii=False)
