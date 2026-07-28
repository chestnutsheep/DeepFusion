"""连板潜力股扫描工具（MCP 自动挂载到 /api/tools/call）。

流程：
1. 取当日涨停股池（akshare 全列，保留流通市值/封单量/封板时间/原因）
2. 回溯最近交易日涨停池代码交集 → 连板高度 board_height
3. 取历史日K线换手率 → 首板/二板换手率对比（二板缩量核心信号）
4. 套 reports.score.evaluate_limit_up 量化评分（8 项 Checklist 阈值）
5. 写入 reports.db limit_up_stocks 表（SQL 回溯），返回排序结果

数据缺口（已在 AGENTS.md 红线外，属新增能力）：
- 封板时间/封单量：直接取 akshare 涨停池全列（market.py 旧工具主动 drop 了，此处不复用）
- 量比/振幅：需 stock_zh_a_spot_em 盘口，非交易时段缺失 → 评分为中性，不阻塞

联网失败/非交易时段：返回说明，不写脏数据。
"""
import akshare as ak
import json

from ..server import mcp
from ..shared.utils import ak_cache, recent_trade_date
from ..reports.store import save_limit_up, get_limit_up
from ..reports.score import evaluate_limit_up


def _val(v, default=""):
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _recent_trade_dates(n=6):
    try:
        df = ak_cache(ak.tool_trade_date_hist_sina, ttl=43200)
        if df is None or df.empty:
            return []
        dates = sorted(df["trade_date"].dt.strftime("%Y%m%d").tolist())
        return dates[-n:]
    except Exception:
        return []


def _zt_pool(dt):
    try:
        df = ak_cache(ak.stock_zt_pool_em, date=dt, ttl=1800)
        if df is None or df.empty:
            return {}
        return {str(r["代码"]): r for _, r in df.iterrows()}
    except Exception:
        return {}


def _board_height(code, dt, dates, pools):
    h = 1
    for prev in reversed([d for d in dates if d != dt]):
        if code in pools.get(prev, {}):
            h += 1
        else:
            break
    return h


def _turnover_pair(code, board_height):
    try:
        df = ak_cache(ak.stock_zh_a_daily, symbol=code, adjust="qfq", ttl=1800)
        if df is None or df.empty or "换手率" not in df.columns:
            return None, None
        vals = df["换手率"].dropna().tolist()
        if len(vals) < 2:
            return (vals[-1] if vals else None), None
        idx1 = -(min(board_height, len(vals)))
        t1 = vals[idx1]            # 首板日换手率
        t2 = vals[-2]              # 昨日换手率（二板日）
        return t1, t2
    except Exception:
        return None, None


@mcp.tool(
    title="连板潜力股扫描",
    description="扫描当日涨停股，回溯连板高度+换手率对比，套8项打板Checklist量化评分，写入reports.db供前端埋伏看板。收盘后运行最佳。",
)
def limit_up_scan(date: str = ""):
    dt = _val(date) or recent_trade_date().strftime("%Y%m%d")
    dates = _recent_trade_dates(6)
    if dt not in dates:
        dates = dates + [dt]

    pools = {d: _zt_pool(d) for d in dates}
    today_pool = pools.get(dt, {})
    if not today_pool:
        return json.dumps({"ok": False,
                           "reason": "非交易时段或当日无涨停数据，请收盘后(15:30后)运行；或今日无涨停股",
                           "date": dt}, ensure_ascii=False)

    iso_date = recent_trade_date().isoformat()
    rows = []
    for code, r in today_pool.items():
        bh = _board_height(code, dt, dates, pools)
        t1, t2 = _turnover_pair(code, bh)
        float_mv = _to_float(r.get("流通市值"))          # 亿元
        limit_price = _to_float(r.get("涨停价")) or _to_float(r.get("最新价"))
        seal_hands = _to_float(r.get("封单量"))           # 手
        # 封单金额(万元) = 手 * 100股 * 涨停价 / 10000
        seal_amount_wan = (seal_hands * 100 * limit_price / 10000.0
                           if seal_hands and limit_price else None)
        seal_time = r.get("最后封板时间") or r.get("封板时间")
        reason = r.get("原因") or ""
        sectors = [s.strip() for s in str(reason).replace("+", ",").split(",") if s.strip()][:3]

        feat = dict(board_height=bh, turnover_1=t1, turnover_2=t2,
                    volume_ratio=None, amplitude=None, seal_time=seal_time,
                    seal_amount=seal_amount_wan, float_mv=float_mv, sectors=sectors)
        ev = evaluate_limit_up(feat)
        rows.append({
            "code": code, "name": r.get("名称"), "board_height": bh,
            "turnover_1": t1, "turnover_2": t2, "volume_ratio": None,
            "amplitude": None, "seal_time": seal_time, "seal_amount": seal_amount_wan,
            "float_mv": float_mv, "score": ev["score"], "stage": ev["stage"],
            "sectors": sectors, "rationale": ev["rationale"], "items": ev["items"],
        })

    rows.sort(key=lambda x: (x["score"] or 0), reverse=True)
    save_limit_up(iso_date, rows)
    return json.dumps({"ok": True, "date": iso_date, "count": len(rows),
                       "stocks": rows}, ensure_ascii=False)


@mcp.tool(
    title="连板潜力股-最新一份",
    description="返回 reports.db 中最新一份连板扫描结果（前端登录看板用）。",
)
def limit_up_latest():
    # 取最近有数据的日期：从 store 读最新（这里取全部日期的最新一条）
    from ..reports.store import _conn
    con = _conn(None)
    try:
        row = con.execute(
            "SELECT DISTINCT date FROM limit_up_stocks ORDER BY date DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return json.dumps({"ok": True, "date": None, "count": 0, "stocks": [],
                           "note": "暂无可回溯的连板数据，请先运行 limit_up_scan"},
                          ensure_ascii=False)
    stocks = get_limit_up(row["date"])
    return json.dumps({"ok": True, "date": row["date"], "count": len(stocks),
                       "stocks": stocks}, ensure_ascii=False)
