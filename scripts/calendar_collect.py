"""大事日历自动采集脚本（定时任务 / 手动刷新按钮触发）。

数据源（akshare，公开日历，无需人工录入）：
- 解禁明细  stock_restricted_release_detail_em(start,end) → 事件日=解禁时间，targets=该股票
- 新股申购  stock_new_ipo_cninfo()                        → 事件日=申购日期，targets=该新股
- 业绩披露预约 stock_report_disclosure(沪深京, 期间)       → 事件日=首次预约，targets=该股票

注意接口兼容性（akshare 1.18.x）：
- 旧 stock_ipo_summary / stock_restricted_release_queue_em 已失效或返回空，改用上面接口。
- stock_yjbb_em(date) 仅接受「报告期」(如 20260331) 且未来期返回 None，不适合按披露日扫描，
  故业绩披露改用 stock_report_disclosure 取「首次预约」日期。

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
from deep_fusion.logging_config import get_logger, configure_logging  # noqa: E402

_LOGGER = get_logger("calendar")
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
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y%m%d")
    try:
        df = ak.stock_restricted_release_detail_em(
            start_date=today.replace("-", ""), end_date=horizon)
    except Exception as ex:
        _LOGGER.warning("restricted_fetch_failed", error=str(ex))
        return out
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        code = str(r.get("股票代码", "")).strip()
        name = str(r.get("股票简称", "")).strip()
        d = _parse_date(r.get("解禁时间"))
        if not code or not d or d < today or d > horizon[:4] + "-" + horizon[4:6] + "-" + horizon[6:]:
            continue
        out.append({
            "date": d, "name": f"{name}解禁", "sector": _stock_industry(code),
            "rating": 3, "category": "解禁", "source": "auto_collect",
            "note": f"解禁明细自动采集（{code}）",
            "domains": _domain_for(code, name),
            "targets": [{"code": code, "name": name}],
        })
    return out


def collect_ipo(days: int, today: str):
    out = []
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = ak.stock_new_ipo_cninfo()
    except Exception as ex:
        _LOGGER.warning("ipo_fetch_failed", error=str(ex))
        return out
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        code = str(r.get("证劵代码", r.get("股票代码", ""))).strip()
        name = str(r.get("证券简称", r.get("股票简称", ""))).strip()
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


def _REPORT_PERIODS():
    """业绩披露预约期间候选列表。

    说明：akshare 的 stock_report_disclosure 仅支持「年报 / 半年报」两种期间标签
    （无 一季报/三季报），且未到披露季的期间会解析失败（数据尚未发布）。
    故此处列出近 2 年的年报/半年报候选，逐个尝试、失败静默跳过（collect_yjbb 已 catch）。
    """
    yr = datetime.now().year
    return [f"{yr}半年报", f"{yr}年报", f"{yr+1}半年报", f"{yr+1}年报"]


def collect_yjbb(days: int, today: str):
    out = []
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    for period in _REPORT_PERIODS():
        try:
            df = ak.stock_report_disclosure(market="沪深京", period=period)
        except Exception as ex:
            _LOGGER.warning("yjbb_fetch_failed", period=period, error=str(ex))
            continue
        if df is None or df.empty:
            continue
        for _, r in df.iterrows():
            code = str(r.get("股票代码", "")).strip()
            name = str(r.get("股票简称", "")).strip()
            d = _parse_date(r.get("首次预约") or r.get("实际披露"))
            if not code or not d or d < today or d > horizon:
                continue
            out.append({
                "date": d, "name": f"{name}业绩披露", "sector": _stock_industry(code),
                "rating": 3, "category": "业绩披露", "source": "auto_collect",
                "note": f"业绩披露预约自动采集（{code}，{period}）",
                "domains": _domain_for(code, name),
                "targets": [{"code": code, "name": name}],
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=75)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    today = date.today().isoformat()
    _LOGGER.info("collect_start", today=today, days=args.days)

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
            _LOGGER.warning("write_failed", name=e['name'], error=str(ex))
    _LOGGER.info("collect_done", written=n)


if __name__ == "__main__":
    configure_logging(os.getenv("DF_LOG_LEVEL", "INFO"))
    main()
