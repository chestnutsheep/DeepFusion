#!/usr/bin/env python3
"""report_writer.py — 将定时任务产出的结构化报告写入 reports.db（历史回溯留档）。

设计：
- 自包含，仅依赖 stdlib sqlite3，**无需安装 DeepFusion**，可供 Claw 项目的自动化脚本直接调用。
- 库路径优先级：--db 参数 > 环境变量 REPORTS_DB_PATH > 默认 <repo>/data/reports.db
  （与 deep_fusion/reports/store.py 的默认路径一致，确保跨项目写同一库）。
- schema 与 deep_fusion/reports/store.py 保持一致；写操作幂等。

用法：
  # 写入/覆盖某类每日报告
  python3 report_writer.py --action save_report --rtype premarket --date 2026-07-29 --json '{"catalyst_count":3,...}'

  # 写入某日连板潜力股列表（JSON 数组）
  python3 report_writer.py --action save_limit_up --date 2026-07-29 --json '[ {"code":"600000",...}, ... ]'

  # 批量导入大事日历事件
  python3 report_writer.py --action seed_calendar --json '[ {"date":"2026-08-04","name":"...","sector":"机器人","rating":5}, ... ]'

  # 新增/更新单条日历事件
  python3 report_writer.py --action calendar_add --date 2026-10-01 --name "..." --sector "..." --rating 4 --category "行业大会"
"""
import argparse
import json
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.getenv("REPORTS_DB_PATH") or os.path.join(REPO, "data", "reports.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rtype TEXT NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(rtype, date)
);
CREATE TABLE IF NOT EXISTS limit_up_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, code TEXT NOT NULL,
    name TEXT, board_height INTEGER, turnover_1 REAL, turnover_2 REAL,
    volume_ratio REAL, amplitude REAL, seal_time TEXT, seal_amount REAL,
    float_mv REAL, score REAL, stage TEXT, sectors TEXT, rationale TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(date, code)
);
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, name TEXT NOT NULL,
    sector TEXT, rating INTEGER DEFAULT 3, category TEXT, source TEXT, note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(date, name)
);
"""


def connect(db_path):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.commit()
    return con


def save_report(con, rtype, rdate, payload):
    con.execute(
        "INSERT OR REPLACE INTO reports(rtype, date, payload, created_at) "
        "VALUES(?,?,?,datetime('now','localtime'))",
        (rtype, rdate, json.dumps(payload, ensure_ascii=False)),
    )
    con.commit()


def save_limit_up(con, rdate, rows):
    for r in rows:
        con.execute(
            "INSERT OR REPLACE INTO limit_up_stocks"
            "(date, code, name, board_height, turnover_1, turnover_2, volume_ratio, "
            " amplitude, seal_time, seal_amount, float_mv, score, stage, sectors, rationale, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))",
            (rdate, r.get("code"), r.get("name"), r.get("board_height"),
             r.get("turnover_1"), r.get("turnover_2"), r.get("volume_ratio"),
             r.get("amplitude"), r.get("seal_time"), r.get("seal_amount"),
             r.get("float_mv"), r.get("score"), r.get("stage"),
             json.dumps(r.get("sectors") or [], ensure_ascii=False), r.get("rationale")),
        )
    con.commit()


def seed_calendar(con, events):
    for e in events:
        con.execute(
            "INSERT OR REPLACE INTO calendar_events"
            "(date, name, sector, rating, category, source, note, created_at) "
            "VALUES(?,?,?,?,?,?,?,datetime('now','localtime'))",
            (e.get("date"), e.get("name"), e.get("sector"), int(e.get("rating", 3)),
             e.get("category"), e.get("source", "manual"), e.get("note", "")),
        )
    con.commit()


def add_calendar_event(con, rdate, name, sector, rating, category):
    con.execute(
        "INSERT OR REPLACE INTO calendar_events"
        "(date, name, sector, rating, category, source, note, created_at) "
        "VALUES(?,?,?,?,?,?,?,datetime('now','localtime'))",
        (rdate, name, sector, int(rating), category, "manual", ""),
    )
    con.commit()


def main():
    p = argparse.ArgumentParser(description="将定时任务结构化报告写入 reports.db（回溯留档）")
    p.add_argument("--db", default=DEFAULT_DB, help="reports.db 路径")
    p.add_argument("--action", required=True, choices=["save_report", "save_limit_up", "seed_calendar", "calendar_add"])
    p.add_argument("--rtype", help="报告类型: premarket/noonnews/qualitystock/dailyreview")
    p.add_argument("--date", help="数据日期 YYYY-MM-DD")
    p.add_argument("--json", help="JSON 字符串（save_report/save_limit_up/seed_calendar 用）")
    p.add_argument("--name", help="calendar_add 事件名")
    p.add_argument("--sector", default="", help="calendar_add 板块")
    p.add_argument("--rating", type=int, default=3, help="calendar_add 评级 1-5")
    p.add_argument("--category", default="", help="calendar_add 类别")
    args = p.parse_args()

    con = connect(args.db)
    try:
        if args.action == "save_report":
            if not args.rtype or not args.date or not args.json:
                sys.exit("save_report 需 --rtype --date --json")
            save_report(con, args.rtype, args.date, json.loads(args.json))
            print(json.dumps({"ok": True, "action": "save_report", "rtype": args.rtype, "date": args.date}))
        elif args.action == "save_limit_up":
            if not args.date or not args.json:
                sys.exit("save_limit_up 需 --date --json")
            rows = json.loads(args.json)
            save_limit_up(con, args.date, rows)
            print(json.dumps({"ok": True, "action": "save_limit_up", "date": args.date, "count": len(rows)}))
        elif args.action == "seed_calendar":
            if not args.json:
                sys.exit("seed_calendar 需 --json")
            events = json.loads(args.json)
            seed_calendar(con, events)
            print(json.dumps({"ok": True, "action": "seed_calendar", "count": len(events)}))
        elif args.action == "calendar_add":
            if not args.date or not args.name:
                sys.exit("calendar_add 需 --date --name")
            add_calendar_event(con, args.date, args.name, args.sector, args.rating, args.category)
            print(json.dumps({"ok": True, "action": "calendar_add", "date": args.date, "name": args.name}))
    finally:
        con.close()


if __name__ == "__main__":
    main()
