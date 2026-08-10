"""金融大事日历工具（MCP 自动挂载到 /api/tools/call）。

功能：
- calendar_seed     : 导入 PART 02 结构化种子事件（10 周催化日程），可重复调用幂等
- calendar_upcoming : 按"今天"返回未来 N 天事件 + 动态 days_until + 埋伏窗口标记（登录看板核心）
- calendar_add      : 新增/更新事件（每月日历维护入口）
- calendar_range    : 区间查询（周/月视图）
- calendar_month    : 某年某月事件

数据来源说明：行业大会/展会/政策会议 akshare 无标准接口，事件表为**人工维护**，
种子数据从用户《连板预测与大事日历》HTML 的 PART 02 结构化提取（标注 source='html_part2'）。
每月需由用户/定时任务补充更新（calendar_add）。
"""
import json
import os
import subprocess
from datetime import date, datetime, timedelta

import akshare as ak

from ..server import mcp
from ..reports.store import (
    seed_calendar, add_calendar_event, get_calendar_upcoming, get_calendar_range,
    get_calendar_event,
)
from ..data.sources import industry_sw
from ..shared import realtime
from ..shared.utils import recent_trade_date


def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 与直接 Python 调用。"""
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


def _val_list(v, default=None):
    """解包 domains/targets 参数：MCP 传入 FieldInfo 或 JSON 字符串，统一解析为 list。"""
    if default is None:
        default = []
    raw = _val(v)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else default
        except json.JSONDecodeError:
            return default
    return default


_BEARISH_SEED = {"医药集采续约", "量化私募新规过渡期结束"}
# 仅标注「已明确落地」的行业利好；政策会议/吹风会/听证会性质的结果未知，不预设方向
_BULLISH_SEED = {
    "海南自贸港封关运作启动", "新能源汽车购置税延续政策落地",
    "新能源汽车下乡启动", "数字货币试点扩围", "数据要素×行动推进",
}


def _seed_sentiment(name):
    """种子事件利好/利空判定（中性为默认，仅对方向明确的事件标注）。"""
    if name in _BEARISH_SEED:
        return "利空"
    if name in _BULLISH_SEED:
        return "利好"
    return "中性"


# ── 年度固定政策发布节点（来自 policy_structure.md Routine 类，仅作日程提醒）──
# (month, day, name, org, category) — 估算日，实际披露以官方为准
ROUTINE_ANNUAL = [
    (1, 15, "国家外汇储备数据月度发布", "国家外汇管理局", "政策发布"),
    (1, 20, "上年四季度国民经济运行情况新闻发布会", "国家统计局", "政策发布"),
    (2, 10, "CPI/PPI 月度数据发布", "国家统计局", "政策发布"),
    (3, 15, "1-2月国民经济运行数据发布", "国家统计局", "政策发布"),
    (4, 15, "一季度GDP初步核算", "国家统计局", "政策发布"),
    (5, 15, "4月国民经济运行数据发布", "国家统计局", "政策发布"),
    (7, 15, "二季度GDP初步核算", "国家统计局", "政策发布"),
    (8, 15, "7月国民经济运行数据发布", "国家统计局", "政策发布"),
    (10, 15, "三季度GDP初步核算", "国家统计局", "政策发布"),
    (10, 20, "专业统计年鉴发布", "国家统计局", "政策发布"),
    (12, 15, "全年国民经济运行情况新闻发布会", "国家统计局", "政策发布"),
]
ROUTINE_QUARTERLY = [
    (3, 20, "货币政策执行报告(季度)", "中国人民银行", "政策发布"),
    (6, 20, "金融市场发展报告(季度)", "中国人民银行", "政策发布"),
    (9, 20, "反洗钱报告(季度)", "中国人民银行", "政策发布"),
]
# (year, name, org, category, is_major)
ROUTINE_CYCLE = [
    (2025, "十五五规划建议", "中国政府网", "政策发布", True),
    (2026, "十五五规划实施", "中国政府网", "政策发布", True),
    (2027, "国防白皮书", "国务院新闻办", "政策发布", False),
    (2028, "人权事业进展白皮书", "国务院新闻办", "政策发布", False),
    (2029, "航天白皮书", "国务院新闻办", "政策发布", False),
    (2030, "十六五规划建议", "中国政府网", "政策发布", True),
]


def calendar_seed_routine():
    """导入年度固定政策发布节点（幂等，可每年重跑以更新次年日程）。

    政策部分的“未来政策节点/倒计时”统一从此读取，避免与工具层硬编码重复。
    """
    from datetime import datetime
    y = datetime.now().year
    events = []
    for yy in (y, y + 1):
        for (mo, day, name, org, cat) in (*ROUTINE_ANNUAL, *ROUTINE_QUARTERLY):
            events.append({"date": f"{yy}-{mo:02d}-{day:02d}", "name": name,
                           "sector": org, "rating": 3, "category": cat,
                           "source": "routine", "sentiment": "中性"})
    for (yy, name, org, cat, major) in ROUTINE_CYCLE:
        events.append({"date": f"{yy}-06-01", "name": name, "sector": org,
                       "rating": 4 if major else 3, "category": cat,
                       "source": "routine", "sentiment": "中性"})
    seed_calendar(events)
    return json.dumps({"ok": True, "count": len(events), "source": "routine"}, ensure_ascii=False)


def ensure_seeded():
    """若日历为空，自动导入 PART 02 种子（部署后首次调用保障前端有埋伏数据）。"""
    if not get_calendar_upcoming(3650):
        events = [{"date": d, "name": n, "sector": s, "rating": r, "category": c,
                   "source": "html_part2", "sentiment": _seed_sentiment(n),
                   "domains": [{"name": s, "type": "auto"}] if s else []}
                  for (d, n, s, r, c) in EVENTS_HTML]
        seed_calendar(events)


# ---- PART 02 结构化种子（从 HTML 提取的初版，需每月核实更新）----
# 字段：date, name, sector, rating(1-5★), category
EVENTS_HTML = [
    ("2026-07-21", "火电价格机制听证会", "电力", 5, "政策会议"),
    ("2026-07-22", "国有资本投资运营公司试点推进会", "国企改革", 3, "政策会议"),
    ("2026-07-23", "国常会(预告)", "全面", 4, "政策会议"),
    ("2026-07-24", "光伏产业链座谈会", "光伏", 4, "行业大会"),
    ("2026-07-25", "科创板开市六周年", "科创", 3, "纪念日"),
    ("2026-07-28", "7月PMI数据发布", "宏观", 4, "数据发布"),
    ("2026-07-29", "消费刺激政策吹风会", "消费", 3, "政策会议"),
    ("2026-07-30", "美联储议息(7/29-7/30)", "全球流动性", 5, "央行议息"),
    ("2026-07-31", "7月官方制造业PMI", "宏观", 4, "数据发布"),
    ("2026-08-01", "海南自贸港封关运作启动", "自贸港", 5, "政策落地"),
    ("2026-08-04", "世界机器人大会(北京)", "机器人", 5, "行业大会"),
    ("2026-08-05", "半导体材料国产化论坛", "半导体", 4, "行业大会"),
    ("2026-08-06", "7月CPI/PPI数据发布", "宏观", 4, "数据发布"),
    ("2026-08-07", "数字货币试点扩围", "数字人民币", 4, "政策落地"),
    ("2026-08-08", "新能源汽车购置税延续政策落地", "新能源车", 4, "政策落地"),
    ("2026-08-11", "生物制造产业大会", "合成生物", 4, "行业大会"),
    ("2026-08-12", "8月MLF续作", "货币", 3, "央行操作"),
    ("2026-08-13", "操作系统大会", "软件/鸿蒙", 4, "行业大会"),
    ("2026-08-14", "商业航天发射窗口", "商业航天", 4, "行业事件"),
    ("2026-08-15", "7月社融信贷数据", "宏观", 4, "数据发布"),
    ("2026-08-18", "世界人工智能大会(WAIC)", "AI", 5, "行业大会"),
    ("2026-08-19", "消费电子秋季发布会(华为)", "消费电子", 4, "行业大会"),
    ("2026-08-20", "LPR报价", "货币", 3, "央行操作"),
    ("2026-08-21", "医药集采续约", "医药", 4, "政策落地"),
    ("2026-08-22", "数据要素×行动推进", "数据要素", 4, "政策落地"),
    ("2026-08-25", "服贸会(北京)", "服务贸易", 4, "行业大会"),
    ("2026-08-26", "量化私募新规过渡期结束", "金融", 3, "监管"),
    ("2026-08-27", "8月工业企业利润", "宏观", 4, "数据发布"),
    ("2026-08-28", "苹果秋季发布会(预期)", "消费电子/苹果链", 5, "行业大会"),
    ("2026-08-29", "稀土整合方案审议", "稀土", 4, "政策会议"),
    ("2026-09-01", "开学季/教育信息化", "教育", 3, "主题"),
    ("2026-09-02", "9月制造业PMI预览", "宏观", 4, "数据发布"),
    ("2026-09-03", "抗战胜利日阅兵(80周年)", "军工/安防", 5, "重大事件"),
    ("2026-09-04", "新能源汽车下乡启动", "新能源车", 4, "政策落地"),
    ("2026-09-05", "数字贸易博览会", "数字贸易", 4, "行业大会"),
    ("2026-09-08", "服贸会闭幕/成果", "服务贸易", 3, "行业大会"),
    ("2026-09-09", "8月CPI/PPI发布", "宏观", 4, "数据发布"),
    ("2026-09-10", "中秋消费旺季开启", "消费", 3, "主题"),
    ("2026-09-11", "9月FOMC议息(9/10-9/11)", "全球流动性", 5, "央行议息"),
    ("2026-09-12", "半导体设备国产化进展", "半导体", 4, "行业大会"),
    ("2026-09-15", "世界计算大会", "算力", 4, "行业大会"),
    ("2026-09-16", "8月社融信贷数据", "宏观", 4, "数据发布"),
    ("2026-09-17", "华为全联接大会", "华为链/算力", 5, "行业大会"),
    ("2026-09-18", "商业航天发射窗口", "商业航天", 4, "行业事件"),
    ("2026-09-19", "美联储点阵图更新", "全球流动性", 4, "央行议息"),
    ("2026-09-22", "世界制造业大会(合肥)", "高端制造", 4, "行业大会"),
    ("2026-09-23", "8月工业企业利润", "宏观", 4, "数据发布"),
    ("2026-09-24", "国庆消费旺季预期", "消费", 3, "主题"),
    ("2026-09-25", "三季度GDP预告", "宏观", 5, "数据发布"),
    ("2026-09-26", "Q3宏观数据发布窗口", "宏观", 4, "数据发布"),
]


@mcp.tool(
    title="大事日历-导入种子",
    description="导入《连板预测与大事日历》PART 02 结构化的10周催化事件（幂等，可重复调用）。",
)
def calendar_seed():
    events = [{"date": d, "name": n, "sector": s, "rating": r, "category": c,
              "source": "html_part2", "sentiment": _seed_sentiment(n)}
              for (d, n, s, r, c) in EVENTS_HTML]
    seed_calendar(events)
    return json.dumps({"ok": True, "imported": len(events),
                       "range": [EVENTS_HTML[0][0], EVENTS_HTML[-1][0]]},
                      ensure_ascii=False)


@mcp.tool(
    title="大事日历-即将发生(埋伏提醒)",
    description="按今天(或指定 as_of)返回未来 days 天的事件，附 days_until 与 bury_window(埋伏窗口)标记。登录看板核心接口。",
)
def calendar_upcoming(days: int = 14, as_of: str = ""):
    ensure_seeded()
    as_of = _val(as_of) or date.today().isoformat()
    rows = get_calendar_upcoming(days=int(days), as_of=as_of)
    return json.dumps({"as_of": as_of, "days": int(days),
                       "count": len(rows), "events": rows}, ensure_ascii=False)


@mcp.tool(
    title="大事日历-新增/更新事件",
    description="新增或更新一条日历事件。每月日历维护入口。",
)
def calendar_add(
        date: str = "", name: str = "", sector: str = "",
        rating: int = 3, category: str = "", sentiment: str = "中性",
        domains: str = "", targets: str = ""):
    date = _val(date)
    if not date or not name:
        return json.dumps({"ok": False, "error": "date 与 name 必填"}, ensure_ascii=False)
    dom = _val_list(domains)
    if not dom and sector:
        dom = [{"name": sector, "type": "auto"}]
    tg = _val_list(targets)
    sentiment = _val(sentiment) or "中性"
    add_calendar_event(date, name, sector, int(rating), category, sentiment,
                       domains=dom, targets=tg)
    return json.dumps({"ok": True, "event": {"date": date, "name": name,
                       "sector": sector, "rating": int(rating), "category": category,
                       "sentiment": sentiment, "domains": dom, "targets": tg}},
                      ensure_ascii=False)


@mcp.tool(
    title="大事日历-区间查询",
    description="查询 [start, end] 区间内的事件（周/月视图用）。",
)
def calendar_range(start: str = "", end: str = ""):
    ensure_seeded()
    start = _val(start)
    end = _val(end)
    if not start or not end:
        return json.dumps({"ok": False, "error": "start/end 必填"}, ensure_ascii=False)
    rows = get_calendar_range(start, end)
    return json.dumps({"start": start, "end": end, "count": len(rows), "events": rows},
                      ensure_ascii=False)


@mcp.tool(
    title="大事日历-月度视图",
    description="返回某年某月的事件，用于月历渲染。",
)
def calendar_month(year: int = 0, month: int = 0):
    ensure_seeded()
    year = int(year) or date.today().year
    month = int(month) or date.today().month
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year+1:04d}-01-01"
    else:
        end = f"{year:04d}-{month+1:02d}-01"
    rows = get_calendar_range(start, end)
    return json.dumps({"year": year, "month": month, "count": len(rows), "events": rows},
                      ensure_ascii=False)


# ===========================================================================
# 关联领域 → 成分股（盘中实时 / 收盘用最近交易日）— 用户要求的"新增实时行情工具"
# ===========================================================================

# 抢跑着色阈值（累计涨幅 from anchor，区间 [event-30td, today]）。
# 注意：以下阈值属展示口径，待量化分析师校准（见 AGENT_BOARD 留言）。
FRONTRUN_RED = 0.30      # 累计涨 ≥30% → 红色：无补涨空间
FRONTRUN_ORANGE = 0.12   # 12%~30% → 橙色：抢跑，尚有空间
FRONTRUN_GREEN = 0.03    # 3%~12% → 绿色：正常进行
# <3% → 蓝色：未被注意 / 仍被低估

_FRONTRUN_COLORS = {
    "red": {"color": "#E25C5C", "label": "已无补涨空间"},
    "orange": {"color": "#E0913C", "label": "抢跑中·尚有空间"},
    "green": {"color": "#4FA86A", "label": "正常进行"},
    "blue": {"color": "#4A78C4", "label": "未被注意·低估"},
}


def _frontrun_status(change: float | None) -> str:
    if change is None:
        return "blue"
    if change >= FRONTRUN_RED:
        return "red"
    if change >= FRONTRUN_ORANGE:
        return "orange"
    if change >= FRONTRUN_GREEN:
        return "green"
    return "blue"


def _sw_name_map():
    """构建 申万 全层级 名称→代码 映射（用于关联领域名称解析）。"""
    try:
        tree = industry_sw.get_tree()
    except Exception:
        return {}
    m = {}

    def walk(nodes):
        for n in nodes:
            if n.get("name") and n.get("code"):
                m[n["name"]] = n["code"]
            if n.get("children"):
                walk(n["children"])
    walk(tree)
    return m


def _resolve_constituents(domain: str, dtype: str, limit: int):
    """解析 关联领域 → [(code, name, weight)]。dtype ∈ industry/concept/sector/auto。"""
    domain = (domain or "").strip()
    if not domain:
        return []
    # 1) 申万行业（industry）：优先用 code，否则用 tree 名称映射
    if dtype in ("industry", "auto"):
        code = domain if domain.isdigit() else ""
        if not code:
            try:
                nm = _sw_name_map()
                code = nm.get(domain, "")
                if not code:  # 模糊：包含匹配
                    for n, c in nm.items():
                        if domain in n or n in domain:
                            code = c
                            break
            except Exception:
                code = ""
        if code:
            try:
                df = industry_sw.get_constituents(code)
                if df is not None and not df.empty:
                    rows = []
                    for _, r in df.iterrows():
                        rows.append((str(r.get("stock_code", "")),
                                     str(r.get("stock_name", "")),
                                     float(r.get("weight") or 0)))
                    rows.sort(key=lambda x: x[2], reverse=True)
                    return rows[:limit]
            except Exception:
                pass
    # 2) 概念板块（concept）
    if dtype in ("concept", "auto"):
        try:
            df = ak.stock_board_concept_cons_em(symbol=domain)
            return [(str(r["代码"]), str(r["名称"]), 0.0) for _, r in df.iterrows()][:limit]
        except Exception:
            pass
    # 3) 行业板块（sector，东方财富行业分类）
    if dtype in ("sector", "auto"):
        try:
            df = ak.stock_board_industry_cons_em(symbol=domain)
            return [(str(r["代码"]), str(r["名称"]), 0.0) for _, r in df.iterrows()][:limit]
        except Exception:
            pass
    return []


@mcp.tool(
    title="日历-关联领域成分股(实时)",
    description="解析关联领域(概念/行业/板块)为成分股，盘中取腾讯实时快照、收盘取最近交易日收盘。"
    "返回 constituents=[{code,name,price,change_pct,turnover,pe,pb}] 与 mode(盘中实时/最近交易日收盘)。",
)
def domain_constituents(domain: str = "", dtype: str = "auto", limit: int = 30):
    domain = _val(domain)
    dtype = _val(dtype) or "auto"
    rows = _resolve_constituents(domain, dtype, int(limit))
    if not rows:
        return json.dumps({"ok": False, "domain": domain, "type": dtype,
                           "error": "未解析到成分股（领域名称可能不匹配申万/概念/行业板块）"},
                          ensure_ascii=False)
    codes = [c for c, _, _ in rows]
    snap = realtime.tencent_realtime(codes)
    mode = realtime.as_of_label()
    cons = []
    for code, name, _ in rows:
        q = snap.get(code, {})
        cons.append({
            "code": code, "name": name,
            "price": q.get("price"), "change_pct": q.get("change_pct"),
            "turnover": q.get("turnover"), "pe": q.get("pe"), "pb": q.get("pb"),
        })
    return json.dumps({"ok": True, "domain": domain, "type": dtype, "mode": mode,
                       "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
                       "count": len(cons), "constituents": cons}, ensure_ascii=False)


# ===========================================================================
# 事件详情 + 抢跑进度
# ===========================================================================

@mcp.tool(
    title="日历-事件详情",
    description="按 id 返回单条事件完整信息（含 domains 关联领域、targets 抢跑标的）。",
)
def calendar_event_detail(event_id: int = 0):
    e = get_calendar_event(int(event_id))
    if e is None:
        return json.dumps({"ok": False, "error": "事件不存在"}, ensure_ascii=False)
    return json.dumps({"ok": True, "event": e}, ensure_ascii=False)


@mcp.tool(
    title="日历-抢跑进度",
    description="计算事件关联标的(event-30交易日 → 今天)的累计涨幅，按蓝/绿/橙/红着色判定抢跑程度。"
    "返回 timeline(进度条锚点/事件日/今天位置) 与 targets(每标的累计涨幅+状态)。无 targets 时返回提示。",
)
def calendar_frontrun(event_id: int = 0, as_of: str = ""):
    e = get_calendar_event(int(event_id))
    if e is None:
        return json.dumps({"ok": False, "error": "事件不存在"}, ensure_ascii=False)
    targets = e.get("targets") or []
    event_date = e["date"]
    as_of = _val(as_of) or date.today().isoformat()
    if not targets:
        return json.dumps({"ok": True, "event_date": event_date, "as_of": as_of,
                           "targets": [],
                           "note": "该事件未标注抢跑标的（人工事件）。自动采集的解禁/新股/业绩预告事件会带真实标的。"},
                          ensure_ascii=False)

    # 以首个标的的交易日序列构建时间轴（A股交易日历一致）
    base_hist = _hist_close(targets[0]["code"], event_date)
    if base_hist is None or len(base_hist) < 2:
        return json.dumps({"ok": True, "event_date": event_date, "as_of": as_of,
                           "targets": [], "note": "暂无历史行情，无法计算抢跑进度。"},
                          ensure_ascii=False)
    dates = [d for d, _ in base_hist]
    event_idx = next((i for i, d in enumerate(dates) if d >= event_date), len(dates) - 1)
    anchor_idx = max(0, event_idx - 30)
    end_idx = min(event_idx + 30, len(dates) - 1)
    current_idx = len(dates) - 1
    span = max(1, end_idx - anchor_idx)

    out_targets = []
    for tg in targets:
        h = _hist_close(tg["code"], event_date)
        if h is None or len(h) <= anchor_idx:
            out_targets.append({**tg, "change_pct": None, "status": "blue",
                                "label": _FRONTRUN_COLORS["blue"]["label"],
                                "anchor_price": None, "current_price": None})
            continue
        hd = [d for d, _ in h]
        hp = [p for _, p in h]
        ai = min(anchor_idx, len(hp) - 1)
        ci = min(current_idx, len(hp) - 1)
        anchor_p, cur_p = hp[ai], hp[ci]
        chg = (cur_p / anchor_p - 1) if anchor_p else None
        st = _frontrun_status(chg)
        out_targets.append({**tg, "change_pct": round(chg, 4) if chg is not None else None,
                            "status": st, "color": _FRONTRUN_COLORS[st]["color"],
                            "label": _FRONTRUN_COLORS[st]["label"],
                            "anchor_price": round(anchor_p, 2),
                            "current_price": round(cur_p, 2)})

    return json.dumps({
        "ok": True,
        "event_date": event_date, "as_of": as_of,
        "timeline": {
            "start": dates[anchor_idx], "event": event_date, "end": dates[end_idx],
            "event_pos": round((event_idx - anchor_idx) / span, 3),
            "today_pos": round((current_idx - anchor_idx) / span, 3),
            "total": span + 1,
        },
        "targets": out_targets,
    }, ensure_ascii=False)


def _hist_close(code: str, event_date: str):
    """取个股 qfq 日线收盘序列（覆盖 event_date 前后 ~80 自然日）。返回 [(date,close)]。"""
    try:
        ed = datetime.strptime(event_date, "%Y-%m-%d")
        start = (ed - timedelta(days=90)).strftime("%Y%m%d")
        end = (ed + timedelta(days=90)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start,
                                end_date=end, adjust="qfq")
        if df is None or df.empty:
            return None
        return [(str(r["日期"]), float(r["收盘"])) for _, r in df.iterrows()]
    except Exception:
        return None


# ===========================================================================
# 半自动采集：触发 scripts/calendar_collect.py（定时任务全自动 + 手动刷新按钮）
# ===========================================================================

@mcp.tool(
    title="日历-刷新采集",
    description="手动触发自动采集脚本 scripts/calendar_collect.py，从解禁/新股/业绩预告等公开日历拉取"
    "事件写入 reports.db。返回采集统计。定时任务也会每日自动跑。",
)
def calendar_refresh_collect():
    script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "calendar_collect.py")
    script = os.path.abspath(script)
    if not os.path.exists(script):
        return json.dumps({"ok": False, "error": f"采集脚本不存在: {script}"}, ensure_ascii=False)
    try:
        import sys
        # 采集含解禁/新股/业绩预约 + 逐股行业查询，数据量大；脚本内部已对单源加超时降级，
        # 整体放宽到 300s。超时也不算失败：日历库已有历史事件，返回降级成功。
        proc = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=300)
        out = (proc.stdout or "") + (proc.stderr or "")
        return json.dumps({"ok": proc.returncode == 0, "returncode": proc.returncode,
                           "log": out[-2000:]}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        # 超时降级：返回既有日历缓存，不阻塞看板
        return json.dumps({"ok": True, "degraded": True,
                           "note": "采集超时，使用既有日历缓存"}, ensure_ascii=False)
    except Exception as ex:
        return json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False)
