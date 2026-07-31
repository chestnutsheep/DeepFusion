"""市场待机快照：大盘指数 / 板块涨跌 / 全市场成交对比 / 资金面（两融·北向·南向·公募·社保·国家队）。

所有数据拉取后落盘到独立 sqlite `market_snapshot.db`（可通过环境变量 MARKET_SNAPSHOT_DB 覆盖），
供前端待机页秒开 + 离线回看。前端通过 `refetchInterval` 触发本工具重新拉取并 upsert。

数据口径与单位说明（重要，前端须如实标注）：
- 单位约定：资金类数值统一以「亿元」为内部单位（akshare 两融/沪深港通/行业资金流原始值即亿元），
  不再额外除以 1e8（旧逻辑误把亿元当元处理导致全部清零，已在真实数据验证中修正）。
- 指数成交额：akshare stock_zh_index_spot_sina 返回单位为「元」，前端/后端换算为亿时用 /1e8。
- 大盘指数：优先 Sina 直连 stock_zh_index_spot_sina（东财 push2 实时域名在本环境不稳定），
  失败回退 stock_zh_index_spot_em(symbol="沪深重要指数")（注意新版 akshare 参数已从 market 改为 symbol）。
- 板块涨跌：stock_fund_flow_industry(symbol="即时") —— 行业涨跌幅 + 主力净额 + 领涨股
  （同时服务于资金面「公募/ETF 偏好」与「国家队代理」）。
- 全市场成交对比：以 上证+深证 成交额合计 近似全市场活跃度，对比「上一交易日」(turnover_history 表按日落盘)得环比。
  刷新(含前端60s自动刷新)只 upsert 当日行，不会污染环比；原始东财日线(含成交额)域名在本环境断连，故改用 Sina 实时 spot 合计。
- 两融余额：stock_margin_account_info 融资余额+融券余额（亿元）最新两期环比。
- 北向资金：港交所自 2024-08 起停止披露北向净买入额，近期为 NaN → 标记 unavailable。
- 南向资金：stock_hsgt_hist_em(symbol="南向资金") 当日成交净买额（亿元）环比。
- 公募/ETF：stock_fund_flow_industry 行业主力净额 Top/Bottom（亿元）。
- 社保/国家队：akshare 无直查接口；国家队以「行业板块主力净额合计」作代理，前端标注"代理/近似"。
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, date

import akshare as ak
import pandas as pd
from pydantic import Field

from ..server import mcp
from ..cache import ak_cache


# 关注的核心指数（中文名，用于从 Sina spot 中筛选）
PRIORITY_INDICES = [
    "上证指数", "深证成指", "创业板指", "沪深300", "上证50",
    "科创50", "中证500", "恒生指数", "科创100",
]


def _db_path() -> str:
    env = os.getenv("MARKET_SNAPSHOT_DB")
    if env:
        return env
    base = os.getenv("DEEP_FUSION_CACHE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "deep_fusion"
    )
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "market_snapshot.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """CREATE TABLE IF NOT EXISTS broad_market (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            snapshot_at TEXT,
            indices TEXT,
            sectors TEXT,
            turnover TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS capital_flows (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            snapshot_at TEXT,
            margin TEXT,
            north TEXT,
            south TEXT,
            public_fund TEXT,
            social_security TEXT,
            nation_team TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS turnover_history (
            date TEXT PRIMARY KEY,
            turnover_yi REAL
        )"""
    )
    conn.commit()
    return conn


def _n(v) -> float | None:
    try:
        if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# 大盘指数（Sina 直连优先，EM 回退）
# ---------------------------------------------------------------------------
def _fetch_indices(force: bool = False) -> list:
    out = []
    df = None
    try:
        df = ak_cache(ak.stock_zh_index_spot_sina, force=force, ttl=120, ttl2=300)
    except Exception:
        df = None
    if df is None or df.empty:
        # 回退东财（注意新版 akshare 用 symbol 而非 market）
        try:
            df = ak_cache(ak.stock_zh_index_spot_em, symbol="沪深重要指数", force=force, ttl=120, ttl2=300)
        except Exception:
            df = None
    if df is None or df.empty:
        return out

    cols = list(df.columns)
    code_c = "代码" if "代码" in cols else (cols[0] if cols else None)
    name_c = "名称" if "名称" in cols else None
    price_c = "最新价" if "最新价" in cols else None
    chg_c = "涨跌额" if "涨跌额" in cols else None
    pct_c = "涨跌幅" if "涨跌幅" in cols else None
    amount_c = "成交额" if "成交额" in cols else None

    seen = set()
    for want in PRIORITY_INDICES:
        sub = df[df[name_c] == want] if name_c else df[df[code_c] == want]
        if sub.empty:
            continue
        r = sub.iloc[0]
        code = str(r.get(code_c, "")) if code_c else ""
        if code in seen:
            continue
        seen.add(code)
        out.append({
            "code": code,
            "name": str(r.get(name_c, want)) if name_c else want,
            "price": _n(r.get(price_c)),
            "change": _n(r.get(chg_c)),
            "change_pct": _n(r.get(pct_c)),
            "amount": _n(r.get(amount_c)),  # 元
        })
    return out


# ---------------------------------------------------------------------------
# 板块涨跌（行业资金流：涨跌幅 + 领涨股 + 主力净额）
# ---------------------------------------------------------------------------
def _fetch_sectors_and_flow(force: bool = False) -> tuple:
    """返回 (sectors, flow_rows)。flow_rows 含 行业/涨跌幅/净额(亿)/领涨股，供多处复用。"""
    sectors, flow_rows = [], []
    try:
        ind = ak_cache(ak.stock_fund_flow_industry, symbol="即时", force=force, ttl=300, ttl2=600)
    except Exception:
        ind = None
    if ind is None or ind.empty:
        return sectors, flow_rows

    cols = list(ind.columns)
    name_c = "行业" if "行业" in cols else (cols[0] if cols else None)
    pct_c = "行业-涨跌幅" if "行业-涨跌幅" in cols else None
    net_c = "净额" if "净额" in cols else None
    lead_c = "领涨股" if "领涨股" in cols else None
    if name_c is None:
        return sectors, flow_rows

    for _, r in ind.iterrows():
        name = str(r.get(name_c, ""))
        pct = _n(r.get(pct_c))
        net = _n(r.get(net_c))  # 亿元
        leader = str(r.get(lead_c, "")) if lead_c else ""
        sectors.append({
            "name": name,
            "change_pct": pct,
            "leader": leader,
            "net_yi": round(net, 1) if net is not None else None,
        })
        flow_rows.append({
            "name": name,
            "net_yi": round(net, 1) if net is not None else None,
        })

    sectors.sort(
        key=lambda x: (x["change_pct"] if x["change_pct"] is not None else -1e9),
        reverse=True,
    )
    flow_rows.sort(
        key=lambda x: (x["net_yi"] if x["net_yi"] is not None else -1e9),
        reverse=True,
    )
    return sectors, flow_rows


# ---------------------------------------------------------------------------
# 全市场成交对比（沪+深成交额合计，对比 DB 基线）
# ---------------------------------------------------------------------------
def _fetch_turnover(indices: list) -> dict | None:
    sh = next((x for x in indices if x["name"] == "上证指数"), None)
    sz = next((x for x in indices if x["name"] == "深证成指"), None)
    if sh is None or sz is None:
        return None
    sh_amt = sh.get("amount")  # 元
    sz_amt = sz.get("amount")  # 元
    if sh_amt is None or sz_amt is None:
        return None
    today_yi = round((sh_amt + sz_amt) / 1e8, 1)  # 元 → 亿
    # 用交易日而非自然日，避免周末/节假日落盘的基线换行错配
    from ..shared.utils import recent_trade_date
    today_date = recent_trade_date().strftime("%Y-%m-%d")
    return {
        "today_yi": today_yi,
        "prev_yi": None,
        "delta_yi": None,
        "delta_pct": None,
        "date": today_date,
        "note": "以沪市+深市成交额合计近似全市场活跃度，对比上一交易日",
    }


def _attach_turnover_baseline(turnover: dict | None, conn: sqlite3.Connection):
    if not turnover:
        return
    today = turnover["date"]
    today_yi = turnover["today_yi"]
    # 记录今日成交额（刷新时 upsert，不污染环比）
    conn.execute(
        "INSERT OR REPLACE INTO turnover_history (date, turnover_yi) VALUES (?,?)",
        (today, today_yi),
    )
    conn.commit()
    # 环比取「上一交易日」的值（date < 今日 的最新一条），与刷新频率无关
    row = conn.execute(
        "SELECT date, turnover_yi FROM turnover_history WHERE date < ? ORDER BY date DESC LIMIT 1",
        (today,),
    ).fetchone()
    if row:
        prev_val, prev_date = row[1], row[0]
        turnover["prev_yi"] = round(prev_val, 1)
        turnover["prev_date"] = prev_date
        turnover["delta_yi"] = round(today_yi - prev_val, 1)
        if prev_val != 0:
            turnover["delta_pct"] = round((today_yi - prev_val) / abs(prev_val) * 100, 2)


# ---------------------------------------------------------------------------
# 资金面
# ---------------------------------------------------------------------------
def _latest_two_pct(rows: list) -> dict | None:
    """从 [{date,value(亿元),value_yi(亿元)}, ...] 取最新两期算环比 delta（单位：亿元）。

    注意：传入的 value 已是「亿元」，不再除以 1e8。
    """
    if len(rows) < 1:
        return None
    today = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    res = {
        "date": today.get("date"),
        "value": today.get("value"),
        "value_yi": today.get("value_yi"),
    }
    if prev:
        v0, v1 = prev.get("value"), today.get("value")
        if v0 is not None and v1 is not None and v0 != 0:
            res["prev_value"] = v0
            res["prev_value_yi"] = prev.get("value_yi")
            res["delta"] = round(v1 - v0, 2)  # 亿
            res["delta_yi"] = round(v1 - v0, 2)  # 亿（前端用）
            res["delta_pct"] = round((v1 - v0) / abs(v0) * 100, 2)
            res["prev_date"] = prev.get("date")
    return res


def _fetch_capital_flows(sectors_flow_rows: list):
    out = {}

    # 两融余额（融资余额 + 融券余额，单位：亿元）
    try:
        mb = ak_cache(ak.stock_margin_account_info, ttl=3600, ttl2=7200)
        if mb is not None and not mb.empty:
            cols = list(mb.columns)
            date_c = "日期" if "日期" in cols else cols[0]
            fin_c = "融资余额" if "融资余额" in cols else None
            loan_c = "融券余额" if "融券余额" in cols else None
            if fin_c or loan_c:
                rows = []
                for _, r in mb.iterrows():
                    fin = _n(r.get(fin_c)) or 0.0
                    loan = _n(r.get(loan_c)) or 0.0
                    v = fin + loan  # 亿元
                    rows.append({"date": str(r.get(date_c, "")), "value": v, "value_yi": round(v, 1)})
                out["margin"] = _latest_two_pct(rows)
    except Exception as e:
        out["margin"] = {"error": str(e)}

    # 北向 / 南向（沪深港通当日成交净买额，单位：亿元）
    for key, label, col_hint in (
        ("北向资金", "north", ["当日成交净买额", "当日资金流入"]),
        ("南向资金", "south", ["当日成交净买额", "当日资金流入"]),
    ):
        try:
            df = ak_cache(ak.stock_hsgt_hist_em, symbol=key, ttl=3600, ttl2=7200)
            if df is not None and not df.empty:
                cols = list(df.columns)
                date_c = "日期" if "日期" in cols else cols[0]
                net_c = None
                for h in col_hint:
                    if h in cols:
                        net_c = h
                        break
                if net_c is None:
                    for c in cols:
                        if "净买" in str(c) or "净流入" in str(c) or "资金流入" in str(c):
                            net_c = c
                            break
                if net_c:
                    # 检查「最新一期」是否仍披露净买入额（北向自2024-08起停披露，近期为NaN）
                    last_val = _n(df[net_c].iloc[-1])
                    last_date = str(df[date_c].iloc[-1])
                    if last_val is None:
                        out[label] = {
                            "available": False,
                            "note": f"{key}：最新一期（{last_date}）无净买入额披露（港交所自2024-08起停止披露北向实时净买入额）",
                        }
                    else:
                        rows = []
                        for _, r in df.iterrows():
                            v = _n(r.get(net_c))  # 亿元（可能为 NaN）
                            if v is None:
                                continue
                            rows.append({"date": str(r.get(date_c, "")), "value": v, "value_yi": round(v, 1)})
                        out[label] = _latest_two_pct(rows) if rows else {
                            "available": False, "note": f"{key}：无有效净买入额数据"
                        }
                else:
                    out[label] = {"available": False, "note": f"{key}：未找到净买额字段"}
        except Exception as e:
            out[label] = {"error": str(e)}

    # 公募基金（ETF）/ 行业资金偏好：来自行业资金流 净额 Top/Bottom（亿元）
    if sectors_flow_rows:
        top = [x for x in sectors_flow_rows if x["net_yi"] is not None][:5]
        bottom = [x for x in sectors_flow_rows if x["net_yi"] is not None][-5:][::-1]
        out["public_fund"] = {
            "top_inflow": top,
            "top_outflow": bottom,
            "note": "以行业板块主力净额近似公募/ETF 资金偏好（代理指标，单位亿元）",
        }
    else:
        out["public_fund"] = {"error": "行业资金流获取失败"}

    # 社保 / 国家队：akshare 无直查，以北向持股市值 + 板块主力净额合计代理
    out["social_security"] = {
        "available": False,
        "note": "akshare 无社保基金持仓变动直查接口；可用北向持股市值 / 板块主力净额作为代理，详见国家队字段",
    }
    try:
        total = 0.0
        for x in sectors_flow_rows:
            if x["net_yi"] is not None:
                total += x["net_yi"]
        out["nation_team"] = {
            "available": True,
            "proxy": "板块主力净额合计（机构合力方向，代理国家队/主力意图，单位亿元）",
            "total_net_yi": round(total, 1),
            "note": "社保/国家队无直查接口，此为主力净额合计代理指标",
        }
    except Exception as e:
        out["nation_team"] = {"error": str(e)}

    return out


@mcp.tool(
    title="市场待机快照（大盘指数+资金面）",
    description="拉取并落盘：大盘重要指数实时涨跌、行业板块涨跌榜、全市场成交额对比上一交易日、"
                "两融余额、北向/南向资金、公募ETF资金偏好、社保/国家队代理指标。用于个股速览待机页。",
)
def market_broad_snapshot(
        force: bool = Field(False, description="绕过缓存强制重新拉取并落盘"),
) -> str:
    indices = _fetch_indices(force=force)
    sectors, _ = _fetch_sectors_and_flow(force=force)
    turnover = _fetch_turnover(indices)
    snap_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "snapshot_at": snap_at,
        "indices": indices,
        "sectors": sectors,
        "turnover": turnover,
        "error": None,
    }
    try:
        conn = _conn()
        # 成交对比：读上次基线 → 计算环比 → 更新基线
        _attach_turnover_baseline(turnover, conn)
        conn.execute(
            "INSERT OR REPLACE INTO broad_market (id, snapshot_at, indices, sectors, turnover) VALUES (1,?,?,?,?)",
            (snap_at, _safe(indices), _safe(sectors), _safe(turnover)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        data["db_error"] = str(e)
    return _safe(data)


@mcp.tool(
    title="资金面快照（两融·北向·南向·公募·社保·国家队）",
    description="拉取并落盘资金面多维动向：两融余额环比、北向/南向资金净流入环比、"
                "公募ETF行业资金偏好、社保/国家队代理指标。用于个股速览待机页。",
)
def capital_flows_snapshot(
        force: bool = Field(False, description="绕过缓存强制重新拉取并落盘"),
) -> str:
    _, flow_rows = _fetch_sectors_and_flow()
    data = _fetch_capital_flows(flow_rows)
    snap_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["snapshot_at"] = snap_at
    try:
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO capital_flows "
            "(id, snapshot_at, margin, north, south, public_fund, social_security, nation_team) "
            "VALUES (1,?,?,?,?,?,?,?)",
            (
                snap_at,
                _safe(data.get("margin")),
                _safe(data.get("north")),
                _safe(data.get("south")),
                _safe(data.get("public_fund")),
                _safe(data.get("social_security")),
                _safe(data.get("nation_team")),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        data["db_error"] = str(e)
    return _safe(data)


@mcp.tool(
    title="读取已落盘市场快照",
    description="从 market_snapshot.db 读取最近一次落盘的大盘指数/资金面快照，前端待机页秒开用。",
)
def market_snapshot_read(
        table: str = Field("all", description="broad_market / capital_flows / all"),
) -> str:
    try:
        conn = _conn()
        result = {}
        if table in ("all", "broad_market"):
            row = conn.execute("SELECT snapshot_at, indices, sectors, turnover FROM broad_market WHERE id=1").fetchone()
            if row:
                result["broad_market"] = {
                    "snapshot_at": row[0],
                    "indices": json.loads(row[1]) if row[1] else [],
                    "sectors": json.loads(row[2]) if row[2] else [],
                    "turnover": json.loads(row[3]) if row[3] else None,
                }
        if table in ("all", "capital_flows"):
            row = conn.execute(
                "SELECT snapshot_at, margin, north, south, public_fund, social_security, nation_team "
                "FROM capital_flows WHERE id=1"
            ).fetchone()
            if row:
                result["capital_flows"] = {
                    "snapshot_at": row[0],
                    "margin": json.loads(row[1]) if row[1] else None,
                    "north": json.loads(row[2]) if row[2] else None,
                    "south": json.loads(row[3]) if row[3] else None,
                    "public_fund": json.loads(row[4]) if row[4] else None,
                    "social_security": json.loads(row[5]) if row[5] else None,
                    "nation_team": json.loads(row[6]) if row[6] else None,
                }
        conn.close()
        return _safe(result)
    except Exception as e:
        return _safe({"error": str(e)})
