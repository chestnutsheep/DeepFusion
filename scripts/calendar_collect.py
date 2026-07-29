"""大事日历自动采集脚本（定时任务 / 手动刷新按钮触发）。

数据源（akshare，公开日历，无需人工录入）：
- 解禁队列  stock_restricted_release_queue_em  → 事件日=解禁日，targets=该股票
- 新股申购  stock_ipo_summary                    → 事件日=申购日，targets=该新股
- 业绩披露  stock_yjbb_em(date)                  → 事件日=预约披露日，targets=该股票

每条事件写 domains(关联领域，取自个股申万行业) 与 targets(抢跑标的，真实代码)，
供前端"关联领域弹窗成分股"与"抢跑进度条"使用。幂等（date+name 唯一）。

用法：
    python scripts/calendar_collect.py [--days 75] [--db data/reports.db]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import akshare as ak  # noqa: E402

from deep_fusion.reports.store import add_calendar_event  # noqa: E402

_INDUSTRY_CACHE: dict[str, str] = {}


def _stock_industry(code: str) -> str:
    """取个股申万/东财行业名（用于关联领域），失败返回空。带进程内缓存。"""
    if code in _INDUSTRY_CACHE:
        return _INDUSTRY_CACHE[code]
    try:
        info = ak.stock_individual_info_em(symbol=code)
        # info: DataFrame[项目, 内容]
        industry = ""
        for _, r in info.iterrows():
            if str(r["项目"]) == "行业":
                industry = str(r["内容"]).strip()
                break
        _INDUSTRY_CACHE[code] = industry
        return industry
    except Exception:
        _INDUSTRY_CACHE[code] = ""
        return ""


def _parse_date(s) -> str | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # 兼容 "2026-08-04" / "2026-08-04 00:00:00" / "2026/08/04"
    s = s.replace("/", "-").split(" ")[0]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def _domain_for(code: str, name: str):
    ind = _stock_industry(code)
    if ind:
        return [{"name": ind, "type": "auto"}]
    return [{"name": name, "type": "auto"}]


def collect_restricted(days: int, today: str):
    out = []
    try:
        df = ak.stock_restricted_release_queue_em(symbol="全部")
    except Exception as ex:
        print(f"[warn] 解禁队列获取失败: {ex}")
        return out
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    for _, r in df.iterrows():
        code = str(r.get("股票代码", "")).strip()
        name = str(r.get("股票简称", "")).strip()
        d = _parse_date(r.get("解禁时间"))
        if not code or not d or d < today or d > horizon:
            continue
        out.append({
            "date": d, "name": f"{name}解禁", "sector": _stock_industry(code),
            "rating": 3, "category": "解禁", "source": "auto_collect",
            "note": f"解禁队列自动采集（{code}）",
            "domains": _domain_for(code, name),
            "targets": [{"code": code, "name": name}],
        })
    return out


def collect_ipo(days: int, today: str):
    out = []
    try:
        df = ak.stock_ipo_summary()
    except Exception as ex:
        print(f"[warn] 新股申购获取失败: {ex}")
        return out
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    for _, r in df.iterrows():
        code = str(r.get("股票代码", "")).strip()
        name = str(r.get("股票简称", "")).strip()
        d = _parse_date(r.get("申购日期") or r.get("上市日期"))
        if not code or not d or d < today or d > horizon:
            continue
        out.append({
            "date": d, "name": f"{name}申购", "sector": _stock_industry(code),
            "rating": 3, "category": "新股", "source": "auto_collect",
            "note": f"新股申购自动采集（{code}）",
            "domains": _domain_for(code, name),
            "targets": [{"code": code, "name": name}],
        })
    return out


def collect_yjbb(days: int, today: str):
    out = []
    horizon_dt = datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)
    # 逐周扫描预约披露日（stock_yjbb_em 按披露日期查询）
    cur = datetime.strptime(today, "%Y-%m-%d")
    while cur <= horizon_dt:
        ds = cur.strftime("%Y%m%d")
        try:
            df = ak.stock_yjbb_em(date=ds)
        except Exception as ex:
            print(f"[warn] 业绩披露 {ds} 获取失败: {ex}")
            cur += timedelta(days=7)
            continue
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                code = str(r.get("股票代码", "")).strip()
                name = str(r.get("股票简称", "")).strip()
                d = _parse_date(r.get("预约披露日期") or r.get("披露日期"))
                if not code or not d or d < today or d > horizon_dt.strftime("%Y-%m-%d"):
                    continue
                out.append({
                    "date": d, "name": f"{name}业绩披露", "sector": _stock_industry(code),
                    "rating": 3, "category": "业绩披露", "source": "auto_collect",
                    "note": f"业绩披露自动采集（{code}）",
                    "domains": _domain_for(code, name),
                    "targets": [{"code": code, "name": name}],
                })
        cur += timedelta(days=7)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=75)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    today = date.today().isoformat()
    print(f"[info] 采集基准日 {today}， horizon +{args.days}d")

    events = []
    events += collect_restricted(args.days, today)
    events += collect_ipo(args.days, today)
    events += collect_yjbb(args.days, today)

    n = 0
    for e in events:
        try:
            add_calendar_event(e["date"], e["name"], e.get("sector", ""), e["rating"],
                               e["category"], e.get("source", "auto_collect"),
                               e.get("note", ""), e.get("domains"), e.get("targets"),
                               db_path=args.db)
            n += 1
        except Exception as ex:
            print(f"[warn] 写入失败 {e['name']}: {ex}")
    print(f"[done] 共写入 {n} 条自动采集事件（date+name 幂等）")


if __name__ == "__main__":
    main()
