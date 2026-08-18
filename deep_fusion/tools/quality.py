"""优质股推送回测 MCP 工具 — 追踪历史推送股的 5 日胜率与反思。

不修改任何既有计算定义（红线）：仅消费 reports.db 的 qualitystock 推送记录 +
market_data.db 的收盘价，做轻量回测聚合。
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

from pydantic import Field

from ..server import mcp


def _val(v, default=None):
    """解包 Field 默认值——兼容 MCP 框架传入的 FieldInfo。"""
    from pydantic.fields import FieldInfo
    if isinstance(v, FieldInfo):
        return v.default if v.default is not None else default
    return v if v is not None else default


def _db_path(env_var, fallback_rel):
    env = os.environ.get(env_var)
    if env and os.path.exists(env):
        return env
    here = os.path.dirname(__file__)
    cand = os.path.join(here, "..", "..", fallback_rel)
    return os.path.abspath(cand)


REPORTS_DB = _db_path("REPORTS_DB_PATH", "data/reports.db")
MARKET_DB = _db_path("MARKET_DATA_DB_PATH", "data/market_data.db")


def _load_quality_batches(days):
    if not os.path.exists(REPORTS_DB):
        return []
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    con = sqlite3.connect(REPORTS_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT date, payload FROM reports WHERE rtype='qualitystock' AND date>=? ORDER BY date",
            (since,),
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        stocks = p.get("stocks") or []
        out.append({"date": r["date"], "stocks": stocks})
    return out


def _calc_return(code, push_date):
    """取 push_date 起最近 6 个交易日的收盘价，算第 5 日相对推送日的收益率。"""
    if not os.path.exists(MARKET_DB):
        return None
    con = sqlite3.connect(MARKET_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT date, close FROM stock_daily WHERE code=? AND date>=? ORDER BY date LIMIT 6",
            (code, push_date),
        ).fetchall()
    finally:
        con.close()
    if len(rows) < 2:
        return None
    base = rows[0]["close"]
    target = rows[min(5, len(rows) - 1)]["close"]
    if not base:
        return None
    return round((target - base) / base * 100, 2)


def _reflect(summary):
    win = summary["win_rate"]
    avg = summary["avg_return"]
    total = summary["total"]
    if total == 0:
        return "暂无足够的历史推送样本，暂无法回测。建议持续观察推送股后续表现。"
    if win >= 60:
        return (
            f"近 {total} 只样本 5 日胜率 {win}%、平均收益 {avg}%，质量因子近期共振良好，"
            "可维持当前选股框架并适度提高仓位权重；注意分散行业以控制单一风格回撤。"
        )
    if win >= 45:
        return (
            f"近 {total} 只样本 5 日胜率 {win}%、平均收益 {avg}，处于临界区间，"
            "市场风格切换中，建议保持现有仓位、不追高，等待胜率与动量重新抬升再加码。"
        )
    return (
        f"近 {total} 只样本 5 日胜率 {win}%、平均收益 {avg}，质量因子近期承压，"
        "小盘/成长风格回撤明显，建议降低推送股仓位、拉长持有周期，或切换至低估防御板块。"
    )


@mcp.tool(name="quality_stock_review")
def quality_stock_review(
    days: int = Field(20, description="回测回溯天数，默认 20 天内的优质股推送"),
) -> str:
    """追踪历史「优质股推送」的 5 日胜率与反思心得。

    读取 reports.db 中 rtype='qualitystock' 的历史推送，结合 market_data.db 收盘价，
    对每只推送股计算推送后 5 个交易日的收益率，聚合胜率与平均收益，并给出反思建议。
    仅供研究参考，不构成投资建议。
    """
    days = _val(days, 20)
    batches = _load_quality_batches(int(days))
    if not batches:
        return json.dumps(
            {"windows": 5, "batches": [], "summary": {"total": 0, "win_rate": 0, "avg_return": 0.0},
             "reflection": _reflect({"total": 0, "win_rate": 0, "avg_return": 0.0})},
            ensure_ascii=False,
        )

    batch_out = []
    all_rets = []
    for b in batches:
        stocks = []
        for s in b["stocks"]:
            code = s.get("code")
            ret = _calc_return(code, b["date"]) if code else None
            if ret is not None:
                all_rets.append(ret)
            stocks.append({
                "code": code,
                "name": s.get("name"),
                "push_price": s.get("price"),
                "ret5": ret,
            })
        wins = [r for r in all_rets if r is not None]  # placeholder, recomputed below
        batch_out.append({
            "date": b["date"],
            "count": len(stocks),
            "stocks": stocks,
        })

    # 聚合（基于已计算的 all_rets）
    valid = [r for r in all_rets if r is not None]
    total = len(valid)
    win_rate = round(sum(1 for r in valid if r > 0) / total * 100, 1) if total else 0
    avg_return = round(sum(valid) / total, 2) if total else 0.0
    summary = {"total": total, "win_rate": win_rate, "avg_return": avg_return}

    # 补全每批次胜率（基于该批次内有效收益）
    for bo in batch_out:
        rs = [s["ret5"] for s in bo["stocks"] if s["ret5"] is not None]
        bo["win_rate"] = round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1) if rs else None
        bo["avg_return"] = round(sum(rs) / len(rs), 2) if rs else None

    result = {
        "windows": 5,
        "batches": batch_out,
        "summary": summary,
        "reflection": _reflect(summary),
        "disclaimer": "股票有风险，入市需谨慎。本回测仅供研究参考，不构成任何投资建议。",
    }
    return json.dumps(result, ensure_ascii=False)
