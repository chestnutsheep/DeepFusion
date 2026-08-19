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


def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 和直接 Python 调用。

    详见 AGENTS.md「MCP 工具注册机制」。新增工具参数统一用此解包。
    """
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


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


# ── 政策板块 → 行业关键词桥接（兜底） ──
# 关键词为主，板块映射兜底：政策 sector 用词较宏观（如"绿色能源"），
# 直接映射为可命中 industry_classify.industry_name 的关键词集合。
_SECTOR_TO_KEYWORDS: dict[str, list[str]] = {
    "宏观金融": ["银行", "证券", "保险", "多元金融", "房地产", "信托", "期货", "数字货币", "金融科技"],
    "房地产基建": ["房地产", "建筑", "建材", "水泥", "钢铁", "工程机械", "装修装饰", "园区开发", "装配式建筑"],
    "绿色能源": ["光伏", "风电", "储能", "电力", "核电", "氢能", "电池", "新能源", "特高压", "电网", "水电", "绿电"],
    "科技数字": ["半导体", "芯片", "人工智能", "软件", "计算机", "云计算", "大数据", "通信", "5G", "消费电子", "面板", "算力", "数据中心"],
    "先进制造": ["工业母机", "机器人", "高端装备", "自动化", "军工", "航天", "无人机", "集成电路", "专精特新"],
    "医疗健康": ["医药", "生物", "医疗", "疫苗", "创新药", "医疗器械", "中药", "CXO", "医疗服务"],
    "消费民生": ["白酒", "食品", "饮料", "零售", "家电", "汽车", "旅游", "酒店", "餐饮", "纺织", "服装", "化妆品", "农牧"],
    "农业农村": ["农业", "种业", "化肥", "农药", "养殖", "饲料", "乡村振兴", "农机"],
    "教育人才": ["教育", "培训", "人力资源", "职业教育"],
    "开放外贸": ["港口", "航运", "物流", "跨境电商", "外贸", "自贸港", "一带一路"],
    "安全环保": ["环保", "水务", "燃气", "网络安全", "信创", "数据安全", "应急"],
    "其他": [],
}


# ── 政策常用词 → 行业名片段 同义词扩展 ──
# 政策口语（"新能源""储能"）≠ 行业分类名（"电池""能源金属"），
# 展开同义词提升关键词命中率（行业分类口径固定，不强行改名）。
_KEYWORD_SYNONYMS: dict[str, list[str]] = {
    "新能源": ["光伏", "风电", "电池", "能源金属", "氢", "绿电", "电网", "核电", "水电", "特高压"],
    "储能": ["电池", "光伏", "风电", "电网", "氢"],
    "光伏": ["光伏", "电池", "能源金属"],
    "风电": ["风电", "电力", "电网", "能源金属"],
    "半导体": ["半导体", "芯片", "集成电路"],
    "芯片": ["半导体", "芯片", "集成电路"],
    "人工智能": ["人工智能", "算力", "计算机", "软件", "云计算", "大数据", "数据中心"],
    "AI": ["人工智能", "算力", "计算机", "软件"],
    "机器人": ["机器人", "自动化", "高端装备", "工业母机"],
    "医药": ["医药", "生物", "医疗", "创新药", "中药", "CXO"],
    "创新药": ["创新药", "医药", "生物", "CXO"],
    "军工": ["军工", "航天", "无人机", "高端装备"],
    "汽车": ["汽车", "新能源车", "电池", "零部件"],
    "消费": ["白酒", "食品", "饮料", "零售", "家电", "汽车", "旅游", "酒店", "服装", "化妆品"],
    "基建": ["建筑", "建材", "水泥", "钢铁", "工程机械", "房地产"],
    "数字经济": ["软件", "计算机", "云计算", "大数据", "通信", "算力", "数据中心", "信创"],
    "信创": ["信创", "软件", "计算机", "网络安全", "数据安全"],
}


def _policy_keywords_terms(keywords: str, sector: str) -> list[str]:
    """把政策的 keywords + sector 展开为可匹配行业名的关键词集合。

    关键词为主（含同义词扩展），板块映射兜底（SECTOR_TO_KEYWORDS 展开）。
    """
    terms: list[str] = []
    if keywords:
        for kw in re.split(r"[,，/、\s]+", keywords):
            kw = kw.strip()
            if not kw:
                continue
            terms.append(kw)
            terms.extend(_KEYWORD_SYNONYMS.get(kw, []))
    if sector:
        for s in re.split(r"[,，/、\s]+", sector):
            s = s.strip()
            if s and s in _SECTOR_TO_KEYWORDS:
                terms.extend(_SECTOR_TO_KEYWORDS[s])
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


@mcp.tool(
    name="policy_market_link",
    description=(
        "政策→市场联动桥接：把一篇政策的 keywords / sector 映射到相关行业板块，"
        "返回匹配行业的近期涨跌、资金净流入、龙头股（来自 meso_industry_fund_flow），"
        "以及代表个股，打通政策与中观/微观数据的联动。供前端『市场联动』面板调用。"
    ),
)
def policy_market_link(
        keywords: str = Field("", description="政策关键词，逗号分隔，如 '新能源,光伏,储能'"),
        sector: str = Field("", description="政策板块，逗号分隔，如 '绿色能源'；用于兜底映射"),
        url: str = Field("", description="政策URL；若提供则从库中取该政策的 keywords/sector，可省略前两个参数"),
        top_n: int = Field(8, description="返回的相关行业最多条数"),
) -> str:
    """返回 JSON：
    - matched_industries: [{industry_name, industry_code, pct_change, net_inflow(亿元),
                            leader_stock, leader_pct_change, match_terms}]
    - representative_stocks: 从匹配行业龙头股去重汇总（最多 12 只）
    - link_method: 'keyword' / 'sector_map' / 'both'
    """
    from ..shared.industry_db import get_classify, get_fund_flow

    # 1. 解析关键词（解包 FieldInfo，兼容框架/直接调用）
    url = _val(url)
    keywords = _val(keywords)
    sector = _val(sector)
    if url:
        from ..shared.policy_db import PolicyDB
        doc = PolicyDB().get(url)
        if not doc:
            return json.dumps({"error": "未找到政策", "found": False}, ensure_ascii=False)
        keywords = keywords or (doc.get("keywords") or "")
        sector = sector or (doc.get("sector") or "")

    terms = _policy_keywords_terms(keywords, sector)
    if not terms:
        return json.dumps(
            {"error": "无可用关键词/板块，无法桥接", "found": False, "terms": []},
            ensure_ascii=False,
        )

    # 2. 行业分类表（行业名 → code）
    classify_df = get_classify("ths")
    name_to_code = {
        str(r["industry_name"]): str(r["industry_code"])
        for _, r in classify_df.iterrows()
    }
    all_names = list(name_to_code.keys())

    # 3. 关键词匹配行业名（包含即命中）
    matched: dict[str, list[str]] = {}
    for name in all_names:
        hit_terms = [t for t in terms if t and t in name]
        if hit_terms:
            matched[name] = hit_terms

    # 4. 资金流（含涨跌/龙头股）
    ff_df = get_fund_flow(limit=200)
    ff_by_name: dict[str, dict] = {}
    for _, r in ff_df.iterrows():
        ff_by_name[str(r["industry_name"])] = {
            "industry_code": str(r["industry_code"]),
            "pct_change": _to_float(r.get("industry_pct_change")),
            "net_inflow": round(_to_float(r.get("net_amount")) or 0.0, 2),  # net_amount 单位已是亿元
            "leader_stock": r.get("leader_stock"),
            "leader_pct_change": _to_float(r.get("leader_pct_change")),
            "company_count": _to_int(r.get("company_count")),
        }

    industries = []
    for name, hit_terms in matched.items():
        ff = ff_by_name.get(name)
        if ff is None:
            # 分类里有但资金流未覆盖（如该行业当日无行情），仍列出
            ff = {"industry_code": name_to_code.get(name, ""), "pct_change": None,
                  "net_inflow": None, "leader_stock": None, "leader_pct_change": None,
                  "company_count": None}
        industries.append({
            "industry_name": name,
            "industry_code": ff["industry_code"],
            "pct_change": ff["pct_change"],
            "net_inflow_yi": ff["net_inflow"],
            "leader_stock": ff["leader_stock"],
            "leader_pct_change": ff["leader_pct_change"],
            "company_count": ff["company_count"],
            "match_terms": hit_terms,
        })

    # 5. 排序：有资金流数据的优先（按净流入），其余靠后
    industries.sort(
        key=lambda x: (x["net_inflow_yi"] is not None, x["net_inflow_yi"] or 0),
        reverse=True,
    )
    industries = industries[:top_n]

    # 6. 代表个股（龙头股去重）
    stocks: list[dict] = []
    seen_stock: set[str] = set()
    for ind in industries:
        ls = ind.get("leader_stock")
        if ls and ls not in seen_stock:
            seen_stock.add(ls)
            stocks.append({
                "stock_name": ls,
                "pct_change": ind.get("leader_pct_change"),
                "from_industry": ind["industry_name"],
            })
        if len(stocks) >= 12:
            break

    # 7. 桥接方法标识
    kw_only = bool(keywords) and not sector
    sec_only = bool(sector) and not keywords
    method = "both" if (keywords and sector) else ("keyword" if kw_only else ("sector_map" if sec_only else "keyword"))

    result = {
        "found": True,
        "terms": terms,
        "link_method": method,
        "matched_count": len(industries),
        "matched_industries": industries,
        "representative_stocks": stocks,
    }
    return json.dumps(result, ensure_ascii=False)


def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v):
    try:
        if v is None or v == "":
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


@mcp.tool(
    name="policy_hot_signals",
    description=(
        "市场舆情热度信号（热点数据采集轮子）：调用本地 Node 热点脚本抓取抖音/微博/百度/"
        "B站/快手实时热搜，作为政策市场关注度的舆情佐证。可筛选含政策/产业关键词的热度条目，"
        "与 policy_daily / policy_market_link 联动。返回 JSON。"
    ),
)
def policy_hot_signals(
        platform: str = Field("all", description="平台: all|douyin|weibo|baidu|bilibili|kuaishou"),
        keyword: str = Field("", description="仅保留标题含该关键词的热度条目（如 '政策,规划,会议'），空=返回全部"),
        top_n: int = Field(20, description="返回条数上限"),
) -> str:
    """返回 JSON：
    - status: ok | error
    - platform
    - count
    - items: [{rank, title, hot, url, platform}]
    """
    from ..data.sources.scrapers import run_hot

    platform = _val(platform, "all")
    keyword = _val(keyword)
    try:
        top_n = int(top_n)
    except (ValueError, TypeError):
        top_n = 20

    raw = run_hot(platform)
    if raw.get("status") != "ok":
        return json.dumps(
            {"status": "error", "message": raw.get("message", "未知错误"), "platform": platform, "items": []},
            ensure_ascii=False,
        )

    items = raw.get("items") or raw.get("data") or []
    # 归一化字段（不同平台脚本输出字段名不一）
    norm = []
    for it in items:
        title = it.get("title") or it.get("word") or it.get("name") or ""
        if not title:
            continue
        norm.append({
            "rank": it.get("rank") or it.get("position") or 0,
            "title": title,
            "hot": it.get("hot") or it.get("heat") or it.get("count") or "",
            "url": it.get("url") or it.get("link") or "",
            "platform": it.get("platform") or platform,
        })

    # 关键词过滤（逗号分隔，任一命中即保留）
    if keyword:
        kws = [k.strip() for k in keyword.split(",") if k.strip()]
        if kws:
            norm = [n for n in norm if any(k in n["title"] for k in kws)]

    norm = norm[:top_n]
    return json.dumps(
        {"status": "ok", "platform": platform, "count": len(norm), "items": norm},
        ensure_ascii=False,
    )


@mcp.tool(
    name="policy_topic_stocks",
    description=(
        "政策主题→个股映射（股票题材猎手轮子）：对政策关键词/板块做『主题→个股』解析。"
        "优先命中本地固化映射（theme_enrich，经 web_search 实测验证），并提供实时检索补全说明，"
        "供 agent 在得到主题后进一步做受益股验证。返回 JSON。"
    ),
)
def policy_topic_stocks(
        topic: str = Field("", description="政策主题/关键词，如 '十五五·商业航天'、'半导体'、'低空经济'"),
        use_static: bool = Field(True, description="是否优先使用本地固化映射（theme_enrich）"),
        enrich_hint: bool = Field(True, description="是否返回『建议实时检索验证』的提示（题材猎手二阶传导）"),
) -> str:
    """返回 JSON：
    - topic
    - matched_static: 命中的本地固化受益股 [{code, name, reason, intensity, next_day}]
    - static_hit: bool
    - search_suggestion: 建议实时检索的查询串（题材猎手方法：主题+政策+A股受益股）
    - note: 方法论说明
    """
    from ..data.sources.scrapers.theme_enrich import enrich_theme_targets

    topic = _val(topic)
    try:
        use_static = bool(use_static)
        enrich_hint = bool(enrich_hint)
    except (ValueError, TypeError):
        use_static, enrich_hint = True, True

    if not topic:
        return json.dumps({"error": "topic 不能为空", "topic": ""}, ensure_ascii=False)

    matched = enrich_theme_targets(topic) if use_static else []
    static_hit = bool(matched)

    # 去重（按 code）
    seen = set()
    matched_unique = []
    for m in matched:
        if m["code"] in seen:
            continue
        seen.add(m["code"])
        matched_unique.append(m)

    suggestion = f"{topic} 政策 A股 受益股 龙头 产业链"
    result = {
        "topic": topic,
        "static_hit": static_hit,
        "matched_static": matched_unique,
        "search_suggestion": suggestion if enrich_hint else "",
        "note": (
            "本地映射经 2026-08-10 web_search 实测验证；新主题（如最新十五五细分方向）"
            "建议用 search_suggestion 实时检索补全，避免静态库滞后。"
        ),
    }
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    name="policy_daily_brief",
    description=(
        "政策每日要闻摘要（新闻摘要轮子，政策语境化）：基于已入库政策按日期聚合，"
        "输出当日/指定日期的政策要闻摘要（机构分布、情绪倾向、关键主题、吹风信号）。"
        "供前端『每日要闻』面板或定时任务播报调用。返回 JSON。"
    ),
)
def policy_daily_brief(
        date: str = Field("", description="指定日期 YYYY-MM-DD；空=取最新入库日"),
        days: int = Field(1, description="聚合最近 N 天政策（date 为空时生效）"),
) -> str:
    """返回 JSON：
    - date / range
    - total
    - by_org: {机构: 条数}
    - sentiment: {利好, 中性, 利空}
    - top_topics: [{topic, count}]（基于 keywords 词频）
    - blow_signals: 吹风源条目 [{org, title, url}]
    - summary: 一句话摘要文本
    """
    from ..shared.policy_db import PolicyDB

    date = _val(date)
    try:
        days = max(1, int(days))
    except (ValueError, TypeError):
        days = 1

    db = PolicyDB()
    docs = db.search(limit=300)  # 取近期批量，本地聚合
    if not docs:
        return json.dumps({"error": "库为空", "total": 0}, ensure_ascii=False)

    # 选定日期窗口
    if date:
        target = date
        window = [d for d in docs if (d.get("publish_date") or "").startswith(target)]
    else:
        # 最新入库日
        dates = sorted({ (d.get("publish_date") or "")[:10] for d in docs if d.get("publish_date") }, reverse=True)
        if not dates:
            return json.dumps({"error": "无有效日期", "total": 0}, ensure_ascii=False)
        target = dates[0]
        # 取最新 days 天
        recent_dates = dates[:days]
        window = [d for d in docs if (d.get("publish_date") or "")[:10] in recent_dates]

    if not window:
        return json.dumps({"error": f"无 {target} 政策", "date": target, "total": 0}, ensure_ascii=False)

    by_org: dict[str, int] = defaultdict(int)
    sentiment = {"利好": 0, "中性": 0, "利空": 0}
    topic_freq: dict[str, int] = defaultdict(int)
    blow: list[dict] = []
    BLOW_ORG = {"新华网", "券商中国"}

    for d in window:
        org = d.get("organization") or d.get("source") or "未知"
        by_org[org] += 1
        s = d.get("sentiment") or "中性"
        if s in sentiment:
            sentiment[s] += 1
        else:
            sentiment["中性"] += 1
        for kw in (d.get("keywords") or "").split(","):
            kw = kw.strip()
            if kw:
                topic_freq[kw] += 1
        if org in BLOW_ORG:
            blow.append({"org": org, "title": d.get("title") or "", "url": d.get("url") or ""})

    top_topics = sorted(
        ({"topic": t, "count": c} for t, c in topic_freq.items()),
        key=lambda x: x["count"], reverse=True
    )[:8]

    total = len(window)
    s_str = f"利好{sentiment['利好']}/中性{sentiment['中性']}/利空{sentiment['利空']}"
    summary = (
        f"{target} 共 {total} 条政策（{s_str}），"
        f"主要来自 {max(by_org, key=by_org.get) if by_org else '—'}，"
        f"焦点：{(top_topics[0]['topic'] if top_topics else '—')}"
        + (f"，含 {len(blow)} 条吹风信号" if blow else "")
    )

    return json.dumps({
        "date": target,
        "range": f"近 {days} 天" if not date else date,
        "total": total,
        "by_org": dict(sorted(by_org.items(), key=lambda x: x[1], reverse=True)),
        "sentiment": sentiment,
        "top_topics": top_topics,
        "blow_signals": blow[:10],
        "summary": summary,
    }, ensure_ascii=False)
