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
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import akshare as ak  # noqa: E402

from deep_fusion.reports.store import add_calendar_event  # noqa: E402
from deep_fusion.logging_config import get_logger, configure_logging  # noqa: E402

_LOGGER = get_logger("calendar")
_INDUSTRY_CACHE: dict[str, str] = {}

# 单次 akshare 网络调用超时（秒）。超时即跳过该源，返回已采集部分，避免整个定时任务卡死。
_AKSHARE_TIMEOUT = int(os.getenv("CALENDAR_AK_TIMEOUT", "45"))


def _with_timeout(fn, *args, **kwargs):
    """给同步 akshare 调用包一层线程超时，超时返回 None 不抛异常。"""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=_AKSHARE_TIMEOUT)
        except FutTimeout:
            _LOGGER.warning("akshare_timeout", fn=fn.__name__)
            return None
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("akshare_error", fn=fn.__name__, error=str(e))
            return None


def _stock_industry(code: str) -> str:
    """取个股申万/东财行业名（用于关联领域），失败/超时返回空。带进程内缓存。"""
    if code in _INDUSTRY_CACHE:
        return _INDUSTRY_CACHE[code]
    try:
        info = _with_timeout(ak.stock_individual_info_em, symbol=code)
        industry = ""
        if info is not None:
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


def _prefill_industries(codes: list[str], max_workers: int = 12):
    """并发批量预热行业缓存（限并发 + 单源超时），避免逐股同步请求累加成百秒级卡死。"""
    uniq = [c for c in dict.fromkeys(codes) if c and c not in _INDUSTRY_CACHE]
    if not uniq:
        return
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(lambda c: _stock_industry(c), uniq))


def _domain_for(code: str, name: str):
    ind = _INDUSTRY_CACHE.get(code, "")
    if ind:
        return [{"name": ind, "type": "auto"}]
    return [{"name": name, "type": "auto"}]


def collect_restricted(days: int, today: str):
    out = []
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y%m%d")
    df = _with_timeout(ak.stock_restricted_release_detail_em,
                       start_date=today.replace("-", ""), end_date=horizon)
    if df is None:
        _LOGGER.warning("restricted_fetch_failed")
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
            "date": d, "name": f"{name}解禁", "sector": "",
            "rating": 3, "category": "解禁", "sentiment": "利空", "source": "auto_collect",
            "note": f"解禁明细自动采集（{code}）",
            "domains": [{"name": name, "type": "auto"}],
            "targets": [{"code": code, "name": name}],
        })
    return out


def collect_ipo(days: int, today: str):
    out = []
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    df = _with_timeout(ak.stock_new_ipo_cninfo)
    if df is None:
        _LOGGER.warning("ipo_fetch_failed")
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
            "date": d, "name": f"{name}申购", "sector": "",
            "rating": 3, "category": "新股", "sentiment": "中性", "source": "auto_collect",
            "note": f"新股申购自动采集（{code}）",
            "domains": [{"name": name, "type": "auto"}],
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
        df = _with_timeout(ak.stock_report_disclosure, market="沪深京", period=period)
        if df is None or df.empty:
            continue
        # 同报告期业绩预告方向映射：给业绩披露事件补 sentiment 维度
        ymap = _yjyg_sentiment_map(period)
        for _, r in df.iterrows():
            code = str(r.get("股票代码", "")).strip()
            name = str(r.get("股票简称", "")).strip()
            d = _parse_date(r.get("首次预约") or r.get("实际披露"))
            if not code or not d or d < today or d > horizon:
                continue
            sent = ymap.get(code, "中性")
            out.append({
                "date": d, "name": f"{name}业绩披露", "sector": "",
                "rating": 3, "category": "业绩披露", "sentiment": sent, "source": "auto_collect",
                "note": f"业绩披露预约自动采集（{code}，{period}）"
                         + (f"，预告{sent}" if sent != "中性" else ""),
                "domains": [{"name": name, "type": "auto"}],
                "targets": [{"code": code, "name": name}],
            })
    return out


# ── 业绩预告方向映射（粗粒度，标注为"主题倾向"）──
# 预增/扭亏/略增 = 利好；预减/首亏/续亏/略减 = 利空；减亏/不确定 = 中性
_YJYG_SENTIMENT = {
    "预增": "利好", "扭亏": "利好", "略增": "利好", "续盈": "利好",
    "预减": "利空", "首亏": "利空", "续亏": "利空", "略减": "利空",
    "减亏": "中性", "不确定": "中性",
}


def _yjyg_periods():
    """业绩预告的报告期候选（akshare 接受 YYYYMMDD 格式）。"""
    yr = datetime.now().year
    return [f"{yr-1}1231", f"{yr}0331", f"{yr}0630", f"{yr}0930", f"{yr}1231"]


def collect_yjyg(days: int, today: str):
    """业绩预告采集：带方向维度（预增/扭亏→利好，预减/首亏→利空）。

    数据源 akshare stock_yjyg_em（东方财富，按报告期拉全量预告）。
    事件日 = 公告日期（预告公开即事件）；同一股票多预测指标行按代码去重，
    保留公告日期最新的一条。仅保留窗口 [today, today+days] 内公告的预告
    （已过去的预告埋伏窗口已过，与 collect_yjbb 只取未来窗口一致）。
    """
    out = []
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    seen: dict[str, dict] = {}
    for period in _yjyg_periods():
        df = _with_timeout(ak.stock_yjyg_em, date=period)
        if df is None or df.empty:
            continue
        for _, r in df.iterrows():
            code = str(r.get("股票代码", "")).strip()
            name = str(r.get("股票简称", "")).strip()
            gdate = _parse_date(r.get("公告日期"))
            if not code or not gdate:
                continue
            if gdate < today or gdate > horizon:
                continue
            ytype = str(r.get("预告类型", "")).strip()
            sent = _YJYG_SENTIMENT.get(ytype, "中性")
            chg = r.get("业绩变动幅度")
            try:
                chg_txt = f"{float(chg):.0f}%" if chg not in (None, "") else ""
            except (TypeError, ValueError):
                chg_txt = str(chg) if chg not in (None, "") else ""
            ev = {
                "date": gdate,
                "name": f"{name}业绩预告·{ytype}",
                "sector": "",
                "rating": 3, "category": "业绩预告", "sentiment": sent,
                "source": "auto_collect",
                "note": f"业绩预告（{ytype}{'，变动' + chg_txt if chg_txt else ''}）",
                "domains": [{"name": name, "type": "auto"}],
                "targets": [{"code": code, "name": name}],
            }
            # 同代码保留公告日期最新的一条
            if code not in seen or gdate > seen[code]["date"]:
                seen[code] = ev
    out.extend(seen.values())
    return out


def _yjyg_date_for(period: str):
    """yjbb 中文期间 → yjyg 报告期 YYYYMMDD；解析失败返回 None。"""
    try:
        y = int(str(period)[:4])
    except (ValueError, TypeError):
        return None
    if "半年报" in str(period):
        return f"{y}0630"
    if "年报" in str(period):
        return f"{y}1231"
    return None


_YJYG_MAP_CACHE: dict[str, dict] = {}


def _yjyg_sentiment_map(period: str) -> dict:
    """该报告期的 股票代码→sentiment 映射（来自业绩预告，带缓存避免重复拉取）。"""
    yjyg_date = _yjyg_date_for(period)
    if not yjyg_date:
        return {}
    if yjyg_date in _YJYG_MAP_CACHE:
        return _YJYG_MAP_CACHE[yjyg_date]
    m: dict = {}
    df = _with_timeout(ak.stock_yjyg_em, date=yjyg_date)
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            code = str(r.get("股票代码", "")).strip()
            if not code or code in m:
                continue
            ytype = str(r.get("预告类型", "")).strip()
            m[code] = _YJYG_SENTIMENT.get(ytype, "中性")
    _YJYG_MAP_CACHE[yjyg_date] = m
    return m


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
    events += collect_yjyg(args.days, today)

    # 并发预热行业缓存（限并发+单源超时），避免逐股同步网络请求累加成百秒级卡死
    all_codes = [e.get("targets", [{}])[0].get("code", "") for e in events if e.get("targets")]
    _prefill_industries(all_codes)
    # 预热后回写 sector/domains（读缓存，不再触发网络）
    for e in events:
        code = e.get("targets", [{}])[0].get("code", "") if e.get("targets") else ""
        name = e["name"]
        if code and _INDUSTRY_CACHE.get(code):
            e["sector"] = _INDUSTRY_CACHE[code]
            e["domains"] = [{"name": _INDUSTRY_CACHE[code], "type": "auto"}]

    n = 0
    for e in events:
        try:
            add_calendar_event(e["date"], e["name"], e.get("sector", ""), e["rating"],
                               e["category"],
                               sentiment=e.get("sentiment", "中性"),
                               source=e.get("source", "auto_collect"),
                               note=e.get("note", ""),
                               domains=e.get("domains"), targets=e.get("targets"),
                               db_path=args.db)
            n += 1
        except Exception as ex:
            _LOGGER.warning("write_failed", name=e['name'], error=str(ex))
    _LOGGER.info("collect_done", written=n)
    # 强制退出：akshare 内部线程/信号量泄漏会导致解释器退出挂起（resource_tracker 警告），
    # 用 os._exit 避免定时任务子进程卡死不返回。
    try:
        _LOGGER.info("force_exit")
    finally:
        os._exit(0)


if __name__ == "__main__":
    configure_logging(os.getenv("DF_LOG_LEVEL", "INFO"))
    main()
