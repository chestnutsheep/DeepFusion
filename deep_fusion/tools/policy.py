"""Policy tracking MCP tools — 国务院政策文件抓取与检索。"""
import json
import re
from collections import defaultdict
from datetime import datetime

from pydantic import Field

from ..data.sources import policy
from ..server import mcp

# ── 官方链接（按机构索引，从数据源配置自动派生） ──
_OFFICIAL_LINKS: dict[str, str] = {
    "国务院": "https://www.gov.cn",
    "国家统计局": "https://www.stats.gov.cn",
    "中国人民银行": "https://www.pbc.gov.cn",
    "国家发改委": "https://www.ndrc.gov.cn",
    "财政部": "https://www.mof.gov.cn",
    "国家外汇管理局": "https://www.safe.gov.cn",
    "国务院新闻办": "http://www.scio.gov.cn",
}

# ── 长周期战略节点（按年份索引，从政策关键词自动补充） ──
_LONG_CYCLE_NODES: list[dict] = [
    {"year": 2025, "label": "十五五规划建议", "is_major": True},
    {"year": 2026, "label": "十五五规划实施", "is_major": True},
    {"year": 2027, "label": "国防/人权白皮书", "is_major": False},
    {"year": 2028, "label": "人权白皮书", "is_major": False},
    {"year": 2029, "label": "航天白皮书", "is_major": False},
    {"year": 2030, "label": "十六五规划建议", "is_major": True},
]

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
) -> str:
    from ..shared.policy_db import PolicyDB
    db = PolicyDB()
    results = db.search(keyword=keyword, org=org, limit=limit, year=year)
    if not results:
        return "无匹配结果"
    lines = [f"共 {len(results)} 条"]
    for r in results:
        kw = f" [{r['keywords']}]" if r.get("keywords") else ""
        org = f" ({r['organization']})" if r.get("organization") else ""
        date = r.get("publish_date", "") or ""
        url = r.get("url", "") or ""
        lines.append(f"  {date:12s} {r['title'][:50]}{org}{kw}  {url}")
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
        return "未找到"
    body = doc.get("body", "")[:2000]
    return json.dumps(
        {k: v for k, v in doc.items() if k != "raw_json"},
        ensure_ascii=False, indent=2,
    ) + f"\n\n正文(前2000字):\n{body}"


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
    results = db.search(limit=500, year=now_year)
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
                    "url": e["url"],
                }
                for e in top
            ],
        })

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
        "long_cycle": _LONG_CYCLE_NODES,
        "official_links": [{"name": k, "url": v} for k, v in _OFFICIAL_LINKS.items()],
        "five_year": {
            "start": five_year_start,
            "end": five_year_end,
            "stage": stage,
        },
    }
    return json.dumps(result, ensure_ascii=False)
