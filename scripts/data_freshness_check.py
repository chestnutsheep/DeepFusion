#!/usr/bin/env python3
"""数据新鲜度自检脚本

扫描所有数据源（diskcache / SQLite / reports.db），核对各维度最新日期，
与今日 / 最近交易日对比，标记断档等级。

用途：
  - 手动跑：uv run python scripts/data_freshness_check.py
  - 定时跑：嵌入 serve.py 或 cron 每日收盘后自动巡检

输出：终端表格 + JSON(可选 `--json logs/data_freshness_report.json`)
退出码：0=全部新鲜 / 1=有警告(无ERROR) / 2=有ERROR
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum


# ── 配置 ────────────────────────────────────────────────────────

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT.parent  # DeepFusion 在 Mcp Server/ 下

# 各 DB 实际路径（非 data/ 下的空壳）
DB_PATHS = {
    "industry_data": PROJECT_ROOT / "data" / "industry_data.db",
    "market_data": PROJECT_ROOT / "data" / "market_data.db",
    "reports": PROJECT_ROOT / "data" / "reports.db",
    # data_lake.db 在 diskcache 目录下（~/.cache/deep_fusion/）
    "policy_cache": pathlib.Path.home() / "output" / "data" / "policy_cache.db",
    "cycle_db": pathlib.Path.home() / "output" / "data" / "cycle_cache.db",
}

# data_lake.db 的路径依赖 diskcache 目录
def _resolve_data_lake() -> pathlib.Path | None:
    """从 deep_fusion.shared.constants 解析 DATA_LAKE_FILE 路径。"""
    try:
        import diskcache
        # diskcache 默认路径
        cache_dir = pathlib.Path.home() / ".cache" / "deep_fusion"
        # 查 constants 里的真实路径
        sys.path.insert(0, str(PROJECT_ROOT))
        from deep_fusion.shared.constants import DATA_LAKE_FILE
        if isinstance(DATA_LAKE_FILE, pathlib.Path):
            return DATA_LAKE_FILE
        return pathlib.Path(str(DATA_LAKE_FILE))
    except Exception:
        return cache_dir / "data_lake.db"


# 最近交易日推算（A股：周一至周五，排除法定节假日暂不考虑）
def _last_trade_date(ref: datetime.date | None = None) -> datetime.date:
    ref = ref or datetime.date.today()
    d = ref
    # 周五→周五，周六→周五，周日→周五
    if d.weekday() == 5:  # 周六
        d = d - datetime.timedelta(days=1)
    elif d.weekday() == 6:  # 周日
        d = d - datetime.timedelta(days=2)
    return d


# ── 数据类 ────────────────────────────────────────────────────────

class Severity(str, Enum):
    OK = "OK"
    WARN = "WARN"   # 轻微滞后 ≤2 天
    STALE = "STALE" # 滞后 >2 天，需关注
    MISSING = "MISSING"  # 无数据

@dataclass
class CheckItem:
    source: str           # 数据库/源名称
    category: str         # 数据类别
    latest_date: str      # 最新数据日期
    expected_date: str    # 预期日期
    lag_days: int         # 滞后天数（日历日）
    lag_trade_days: int   # 滞后交易日数
    rows: int = 0
    severity: Severity = Severity.OK
    detail: str = ""


# ── 检查函数 ────────────────────────────────────────────────────────

def _db_exists(path: pathlib.Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _max_date(con: sqlite3.Connection, table: str, col: str) -> tuple[str | None, int]:
    try:
        r = con.execute(f"SELECT MAX({col}), COUNT(*) FROM {table}").fetchone()
        return r[0], r[1] if r else (None, 0)
    except Exception:
        return None, 0


def _check_industry(ref: datetime.date, trade: datetime.date) -> list[CheckItem]:
    items = []
    db = DB_PATHS["industry_data"]
    if not _db_exists(db):
        items.append(CheckItem("industry_data", "整个库", "-", str(ref), 999, 999, severity=Severity.MISSING, detail="文件不存在或为空"))
        return items
    con = sqlite3.connect(str(db))
    try:
        # industry_daily
        d, rows = _max_date(con, "meso_industry_daily", "trade_date")
        lag = (trade - datetime.date.fromisoformat(d)).days if d else 999
        sv = Severity.OK if lag <= 0 else (Severity.WARN if lag <= 2 else Severity.STALE)
        items.append(CheckItem("industry_data", "行业日线(trade_date)", d or "-", str(trade), lag, max(0, lag), rows=rows, severity=sv))

        # fund_flow
        d2, rows2 = _max_date(con, "meso_industry_fund_flow", "updated_at")
        if d2:
            d2_date = d2[:10]
            lag2 = (trade - datetime.date.fromisoformat(d2_date)).days
            sv2 = Severity.OK if lag2 <= 0 else (Severity.WARN if lag2 <= 2 else Severity.STALE)
        else:
            d2_date, lag2, sv2, rows2 = "-", 999, Severity.MISSING, 0
        items.append(CheckItem("industry_data", "行业资金流(updated_at)", d2_date, str(trade), lag2, max(0, lag2), rows=rows2, severity=sv2))

        # financial
        d3, rows3 = _max_date(con, "meso_industry_financial", "trade_date")
        if d3:
            lag3 = (trade - datetime.date.fromisoformat(d3)).days
            sv3 = Severity.OK if lag3 <= 0 else (Severity.WARN if lag3 <= 2 else Severity.STALE)
        else:
            d3, lag3, sv3, rows3 = "-", 999, Severity.MISSING, 0
        items.append(CheckItem("industry_data", "行业财务(trade_date)", d3 or "-", str(trade), lag3, max(0, lag3), rows=rows3, severity=sv3))

    finally:
        con.close()
    return items


def _check_market(ref: datetime.date, trade: datetime.date) -> list[CheckItem]:
    items = []
    db = DB_PATHS["market_data"]
    if not _db_exists(db):
        items.append(CheckItem("market_data", "整个库", "-", str(ref), 999, 999, severity=Severity.MISSING))
        return items
    con = sqlite3.connect(str(db))
    try:
        # stock_daily
        d, rows = _max_date(con, "stock_daily", "date")
        lag = (trade - datetime.date.fromisoformat(d)).days if d else 999
        sv = Severity.OK if lag <= 0 else (Severity.WARN if lag <= 2 else Severity.STALE)
        n_stocks = con.execute("SELECT COUNT(DISTINCT code) FROM stock_daily WHERE date=?", (d,)).fetchone()[0] if d else 0
        items.append(CheckItem("market_data", f"个股日线(date) [{n_stocks}只]", d or "-", str(trade), lag, max(0, lag), rows=rows, severity=sv))

        # index_daily
        d2, rows2 = _max_date(con, "index_daily", "date")
        if d2:
            lag2 = (trade - datetime.date.fromisoformat(d2)).days
            sv2 = Severity.OK if lag2 <= 0 else (Severity.WARN if lag2 <= 2 else Severity.STALE)
        else:
            d2, lag2, sv2, rows2 = "-", 999, Severity.MISSING, 0
        items.append(CheckItem("market_data", "指数日线(date)", d2 or "-", str(trade), lag2, max(0, lag2), rows=rows2, severity=sv2))

    finally:
        con.close()
    return items


def _check_reports(ref: datetime.date) -> list[CheckItem]:
    items = []
    db = DB_PATHS["reports"]
    if not _db_exists(db):
        items.append(CheckItem("reports", "整个库", "-", str(ref), 999, 999, severity=Severity.MISSING))
        return items
    con = sqlite3.connect(str(db))
    try:
        # limit_up_stocks
        d, rows = _max_date(con, "limit_up_stocks", "date")
        lag = (ref - datetime.date.fromisoformat(d)).days if d else 999
        sv = Severity.OK if lag <= 0 else (Severity.WARN if lag <= 2 else Severity.STALE)
        items.append(CheckItem("reports", "连板潜力股(date)", d or "-", str(ref), lag, max(0, lag), rows=rows, severity=sv))

        # dailyscan
        r = con.execute("SELECT COUNT(*) FROM reports WHERE rtype='dailyscan'").fetchone()
        rows2 = r[0] if r else 0
        if rows2 == 0:
            items.append(CheckItem("reports", "每日选股(dailyscan)", "-", str(ref), 999, 999, rows=0, severity=Severity.MISSING))
        else:
            r2 = con.execute("SELECT MAX(date), MAX(created_at) FROM reports WHERE rtype='dailyscan'").fetchone()
            d2 = r2[0] or r2[1]
            if d2:
                lag2 = (ref - datetime.date.fromisoformat(d2[:10])).days
                sv2 = Severity.OK if lag2 <= 0 else (Severity.WARN if lag2 <= 2 else Severity.STALE)
            else:
                d2, lag2, sv2 = "-", 999, Severity.MISSING
            items.append(CheckItem("reports", "每日选股(date)", str(d2), str(ref), lag2, max(0, lag2), rows=rows2, severity=sv2))

        # premarket / noonnews / qualitystock (由 automations 写入)
        for rtype, label in [("premarket", "盘前简报"), ("noonnews", "午间推送"), ("qualitystock", "优质股推送")]:
            r3 = con.execute("SELECT MAX(date) FROM reports WHERE rtype=? AND date < '2099-01-01'", (rtype,)).fetchone()
            if r3 and r3[0]:
                lag3 = (ref - datetime.date.fromisoformat(r3[0])).days
                sv3 = Severity.OK if lag3 <= 0 else (Severity.WARN if lag3 <= 2 else Severity.STALE)
                items.append(CheckItem("reports", label, r3[0], str(ref), lag3, max(0, lag3), severity=sv3))
            else:
                items.append(CheckItem("reports", label, "-", str(ref), 999, 999, severity=Severity.MISSING))

        # calendar_events
        d4, rows4 = _max_date(con, "calendar_events", "created_at")
        if d4:
            d4_str = d4[:10]
            lag4 = (ref - datetime.date.fromisoformat(d4_str)).days
            sv4 = Severity.OK if lag4 <= 2 else (Severity.WARN if lag4 <= 7 else Severity.STALE)
        else:
            d4_str, lag4, sv4, rows4 = "-", 999, Severity.MISSING, 0
        items.append(CheckItem("reports", "大事日历(created_at)", d4_str, str(ref), lag4, max(0, lag4), rows=rows4, severity=sv4))

    finally:
        con.close()
    return items


def _check_data_lake(ref: datetime.date) -> list[CheckItem]:
    items = []
    db = _resolve_data_lake()
    if not db or not _db_exists(db):
        items.append(CheckItem("data_lake", "整个库", "-", str(ref), 999, 999, severity=Severity.MISSING, detail=f"路径:{db}"))
        return items
    con = sqlite3.connect(str(db))
    try:
        # macro_data 各指标最新日期
        cols = [d[1] for d in con.execute("PRAGMA table_info(macro_data)")]
        date_col = "period" if "period" in cols else "date"
        for indicator, label in [
            ("CPI", "CPI"), ("PPI", "PPI"), ("PMI", "PMI"),
            ("FIXED_INVESTMENT", "固定资产投资"), ("GDP", "GDP"), ("M2", "M2货币供应"),
        ]:
            r = con.execute(
                f"SELECT MAX({date_col}), COUNT(*) FROM macro_data WHERE indicator=?",
                (indicator,)
            ).fetchone()
            d, rows = r[0], r[1] if r else (None, 0)
            if d:
                # 经济指标格式通常是 YYYY-MM 或 YYYY年MM月份 或 YYYY-QQ
                # 滞后期判定：月频指标 ≤45 天 = OK
                try:
                    if "-" in d and d.count("-") >= 2:
                        dt = datetime.date.fromisoformat(d[:10] if len(d) > 10 else d)
                    elif "季度" in d:
                        # 季度数据：如 "2026年第1季度"
                        import re
                        m = re.match(r"(\d{4})\D*(\d)", d)
                        if m:
                            y, q = int(m.group(1)), int(m.group(2))
                            dt = datetime.date(y, q * 3, 1)  # 季度末月第一天
                        else:
                            dt = ref
                    elif "年" in d or "月" in d:
                        import re
                        m = re.match(r"(\d{4})年(\d{1,2})月份", d)
                        if m:
                            y, mo = int(m.group(1)), int(m.group(2))
                            dt = datetime.date(y, mo, 1)
                        else:
                            dt = ref
                    else:
                        dt = ref
                    lag = (ref - dt).days
                except Exception:
                    lag = 0  # 无法解析的格式，默认 OK
                max_lag = 60 if indicator in ("GDP",) else 45  # 月频≤45天，季频≤60天
                sv = Severity.OK if lag <= max_lag else (Severity.WARN if lag <= 90 else Severity.STALE)
            else:
                d, lag, sv, rows = "-", 999, Severity.MISSING, 0
            items.append(CheckItem("data_lake", label, str(d), str(ref), lag, 0, rows=rows, severity=sv))

    finally:
        con.close()
    return items


def _check_policy(ref: datetime.date) -> list[CheckItem]:
    items = []
    db = DB_PATHS["policy_cache"]
    if not _db_exists(db):
        items.append(CheckItem("policy_cache", "整个库", "-", str(ref), 999, 999, severity=Severity.MISSING, detail=f"路径:{db}"))
        return items
    con = sqlite3.connect(str(db))
    try:
        d, rows = _max_date(con, "policy_docs", "found_at")
        if d:
            d_str = d[:10] if "T" in d else d
            lag = (ref - datetime.date.fromisoformat(d_str)).days
            sv = Severity.OK if lag <= 0 else (Severity.WARN if lag <= 2 else Severity.STALE)
        else:
            d_str, lag, sv, rows = "-", 999, Severity.MISSING, 0
        items.append(CheckItem("policy_cache", "政策文档(found_at)", d_str, str(ref), lag, max(0, lag), rows=rows, severity=sv))
    finally:
        con.close()
    return items


# ── 主函数 ────────────────────────────────────────────────────────

def run_check(ref_date: datetime.date | None = None) -> list[CheckItem]:
    ref = ref_date or datetime.date.today()
    trade = _last_trade_date(ref)
    items: list[CheckItem] = []
    items.extend(_check_industry(ref, trade))
    items.extend(_check_market(ref, trade))
    items.extend(_check_reports(ref))
    items.extend(_check_data_lake(ref))
    items.extend(_check_policy(ref))
    return items


def format_table(items: list[CheckItem]) -> str:
    """终端表格输出"""
    COLOR = {
        Severity.OK: "\033[32m",
        Severity.WARN: "\033[33m",
        Severity.STALE: "\033[31m",
        Severity.MISSING: "\033[35m",
    }
    RST = "\033[0m"
    header = f"{'数据源':<16} {'类别':<22} {'最新日期':<14} {'预期':<10} {'滞后':>5} {'行数':>8} 状态"
    sep = "-" * len(header.expandtabs())
    lines = [f"\n{sep}\n数据新鲜度巡检 — {datetime.date.today()}\n{sep}", header, sep]
    for it in items:
        c = COLOR.get(it.severity, "")
        lag_str = f"{it.lag_days}d" if it.lag_days < 999 else "∞"
        lines.append(
            f"{it.source:<16} {it.category:<22} {it.latest_date:<14} "
            f"{it.expected_date:<10} {lag_str:>5} {it.rows:>8}  "
            f"{c}{it.severity.value:<6}{RST}"
        )
    lines.append(sep)

    # 统计摘要
    ok = sum(1 for it in items if it.severity == Severity.OK)
    warn = sum(1 for it in items if it.severity == Severity.WARN)
    stale = sum(1 for it in items if it.severity == Severity.STALE)
    missing = sum(1 for it in items if it.severity == Severity.MISSING)
    total = len(items)
    stales_details = [it for it in items if it.severity in (Severity.STALE, Severity.MISSING)]
    lines.append(f"\n总计 {total} 项: {COLOR[Severity.OK]}{ok} OK{RST} | "
                 f"{COLOR[Severity.WARN]}{warn} WARN{RST} | "
                 f"{COLOR[Severity.STALE]}{stale} STALE{RST} | "
                 f"{COLOR[Severity.MISSING]}{missing} MISSING{RST}")
    lines.append(f"最近交易日: {_last_trade_date()}")

    if stales_details:
        lines.append(f"\n⚠️  需修复 ({len(stales_details)} 项):")
        for it in stales_details:
            lines.append(f"  - [{it.source}] {it.category}: "
                         f"最新 {it.latest_date}, "
                         f"{'无数据，从未采集' if it.lag_days >= 999 else f'滞后 {it.lag_days} 天'}")
            if it.detail:
                lines.append(f"    {it.detail}")
    else:
        lines.append("\n✅ 全部数据新鲜度正常！")

    return "\n".join(lines)


def to_json(items: list[CheckItem]) -> dict:
    return {
        "date": str(datetime.date.today()),
        "trade_date": str(_last_trade_date()),
        "total": len(items),
        "summary": {
            "ok": sum(1 for it in items if it.severity == Severity.OK),
            "warn": sum(1 for it in items if it.severity == Severity.WARN),
            "stale": sum(1 for it in items if it.severity == Severity.STALE),
            "missing": sum(1 for it in items if it.severity == Severity.MISSING),
        },
        "items": [
            {
                "source": it.source, "category": it.category,
                "latest_date": it.latest_date, "expected_date": it.expected_date,
                "lag_days": it.lag_days, "lag_trade_days": it.lag_trade_days,
                "rows": it.rows, "severity": it.severity.value,
                "detail": it.detail,
            }
            for it in items
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="数据新鲜度自检")
    parser.add_argument("--json", type=str, metavar="PATH", help="导出 JSON 报告")
    parser.add_argument("--quiet", action="store_true", help="仅输出摘要")
    parser.add_argument("--exit-code", action="store_true", default=True,
                        help="按严重度退出(0=OK,1=WARN,2=STALE+)")
    args = parser.parse_args()

    items = run_check()

    if args.json:
        report = to_json(items)
        pathlib.Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"JSON 报告已写入: {args.json}")

    if args.quiet:
        ok = sum(1 for it in items if it.severity == Severity.OK)
        warn = sum(1 for it in items if it.severity == Severity.WARN)
        stale = sum(1 for it in items if it.severity == Severity.STALE)
        missing = sum(1 for it in items if it.severity == Severity.MISSING)
        print(f"[freshness] {ok}OK {warn}WARN {stale}STALE {missing}MISSING")
    else:
        print(format_table(items))

    if args.exit_code:
        has_stale = any(it.severity in (Severity.STALE, Severity.MISSING) for it in items)
        has_warn = any(it.severity == Severity.WARN for it in items)
        if has_stale:
            sys.exit(2)
        elif has_warn:
            sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
