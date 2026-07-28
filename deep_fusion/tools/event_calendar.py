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
from datetime import date, datetime

from ..server import mcp
from ..reports.store import (
    seed_calendar, add_calendar_event, get_calendar_upcoming, get_calendar_range,
)
from ..shared.utils import recent_trade_date


def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 与直接 Python 调用。"""
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


def ensure_seeded():
    """若日历为空，自动导入 PART 02 种子（部署后首次调用保障前端有埋伏数据）。"""
    if not get_calendar_upcoming(3650):
        events = [{"date": d, "name": n, "sector": s, "rating": r, "category": c,
                  "source": "html_part2"} for (d, n, s, r, c) in EVENTS_HTML]
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
              "source": "html_part2"} for (d, n, s, r, c) in EVENTS_HTML]
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
        rating: int = 3, category: str = ""):
    date = _val(date)
    if not date or not name:
        return json.dumps({"ok": False, "error": "date 与 name 必填"}, ensure_ascii=False)
    add_calendar_event(date, name, sector, int(rating), category)
    return json.dumps({"ok": True, "event": {"date": date, "name": name,
                       "sector": sector, "rating": int(rating), "category": category}},
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
