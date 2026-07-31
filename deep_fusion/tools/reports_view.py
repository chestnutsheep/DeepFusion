"""每日报告读取工具（MCP 自动挂载到 /api/tools/call）。

供前端「每日看板」消费四个定时任务(premarket/noonnews/qualitystock/dailyreview)
写入 reports.db 的最新结构化报告。读取端，不修改任何计算定义。
"""
import json

from ..server import mcp
from ..reports.store import get_latest, get_history, get_by_date, _conn
from .event_calendar import _val


@mcp.tool(
    title="每日报告-最新",
    description="读取某类定时任务报告最新一份(reports 表)。rtype: premarket/noonnews/qualitystock/dailyreview",
)
def report_latest(rtype: str = ""):
    rtype = _val(rtype)
    if not rtype:
        return json.dumps({"ok": False, "error": "rtype 必填"}, ensure_ascii=False)
    row = get_latest(rtype)
    if not row:
        return json.dumps({"ok": True, "rtype": rtype, "date": None, "payload": None,
                           "note": "暂无数据，定时任务尚未写入"}, ensure_ascii=False)
    return json.dumps({"ok": True, "rtype": rtype, "date": row["date"],
                       "payload": row["payload"]}, ensure_ascii=False)


@mcp.tool(
    title="每日报告-历史",
    description="读取某类报告最近 limit 份（历史回溯）。",
)
def report_history(rtype: str = "", limit: int = 10):
    rtype = _val(rtype)
    limit = int(limit)
    rows = get_history(rtype, limit)
    return json.dumps({"ok": True, "rtype": rtype, "count": len(rows), "history": rows},
                      ensure_ascii=False)


@mcp.tool(
    title="每日报告-类型列表",
    description="列出 reports 表中已入库的报告类型。",
)
def report_types():
    con = _conn(None)
    try:
        rows = con.execute("SELECT DISTINCT rtype FROM reports ORDER BY rtype").fetchall()
    finally:
        con.close()
    return json.dumps({"ok": True, "types": [r["rtype"] for r in rows]}, ensure_ascii=False)


@mcp.tool(
    title="每日报告-按日期",
    description="按 (rtype, 日期) 读取某类报告的指定日期内容(reports 表)。rtype: premarket/noonnews/qualitystock/dailyreview；rdate: YYYY-MM-DD",
)
def report_by_date(rtype: str = "", rdate: str = ""):
    rtype = _val(rtype)
    rdate = _val(rdate)
    if not rtype or not rdate:
        return json.dumps({"ok": False, "error": "rtype 与 rdate 必填"}, ensure_ascii=False)
    row = get_by_date(rtype, rdate)
    if not row:
        return json.dumps({"ok": True, "rtype": rtype, "date": rdate, "payload": None,
                           "note": "该日期暂无报告"}, ensure_ascii=False)
    return json.dumps({"ok": True, "rtype": rtype, "date": row["date"],
                       "payload": row["payload"]}, ensure_ascii=False)
