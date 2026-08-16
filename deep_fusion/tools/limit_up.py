"""连板潜力股扫描工具（MCP 自动挂载到 /api/tools/call）。

流程：
1. 取当日涨停股池（akshare 全列，保留流通市值/封单量/封板时间/原因）
2. 回溯最近交易日涨停池代码交集 → 连板高度 board_height
3. 取历史日K线换手率 → 首板/二板换手率对比（二板缩量核心信号）
4. 套 reports.score.evaluate_limit_up 量化评分（8 项 Checklist 阈值）
5. 写入 reports.db limit_up_stocks 表（SQL 回溯），返回排序结果

数据契约（量化校准修正，2026-07-29）：
- 流通市值：akshare 给「元」→ 转「亿元」再入 score（原直接当亿元，导致全市场否决）。
- 封单金额：涨停池列名是「封板资金」(元)，**无「封单量」列** → 用封板资金/1e4 转万元。
- 封板时间：akshare 给 HHMMSS，score._score_seal_time 已兼容解析。
- 量比/振幅：原依赖盘口 spot（非交易时段缺失）；现改为从日K推算（收盘后可用），
  量比=当日量/前5日均量，振幅=(高-低)/昨收，补「量比/振幅缺口」。

联网失败/非交易时段：返回说明，不写脏数据。
"""
import akshare as ak
import json
import logging
import os
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

from ..server import mcp
from ..shared.utils import ak_cache, recent_trade_date
from ..reports.store import save_limit_up, get_limit_up, save_report, get_latest
from ..reports.score import evaluate_limit_up, calibrated_probability


# 实证校准结果落盘位置（score_calibrate.py 默认输出），limit_up_scan 自动采用。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CALIB_PATH = os.path.join(_REPO_ROOT, "data", "score_calibration.json")


def _val(v, default=""):
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


def _load_calibration_weights():
    """读取 data/score_calibration.json 的 recommended_weights；无则回退默认权重。"""
    try:
        if os.path.exists(_CALIB_PATH):
            with open(_CALIB_PATH, encoding="utf-8") as f:
                rep = json.load(f)
            w = rep.get("recommended_weights")
            if w:
                return w
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("calibration_load_corrupt", path=_CALIB_PATH, error=str(e))
        _backup_corrupt(_CALIB_PATH)
    return None


def _load_calibration():
    """读取 data/score_calibration.json 完整 dict（platt_fit/per_item_hit_rate/board_height_rate/base_rate）。"""
    try:
        if os.path.exists(_CALIB_PATH):
            with open(_CALIB_PATH, encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("calibration_load_corrupt", path=_CALIB_PATH, error=str(e))
        _backup_corrupt(_CALIB_PATH)
    return None


def _backup_corrupt(path: str) -> None:
    """校准文件损坏时备份坏文件，避免下次读取再次崩溃且无迹可查（对齐 shared/utils._safe_json）。"""
    bad = path + ".corrupt"
    try:
        if os.path.exists(path):
            os.replace(path, bad)
    except OSError:
        pass


def _proxy_score(items, weights):
    """4 因子加权代理分（供 Platt）：items 为名次(score,weight)-list，weights 为权重表。"""
    if not weights:
        return None
    num = den = 0.0
    for it in items:
        wt = weights.get(it["name"])
        if wt:
            num += it["score"] * wt
            den += wt
    return num / den if den else None


# Platt 训练用的 4 因子权重，须与 score_calibrate.fit_platt 的 wmap 保持一致
# （仅可驱动因子：换手率/封板时间/流通市值/封单比），否则 p_cal 与训练分布不符
_PLATT_WMAP = {"换手率": 18, "封板时间": 18, "流通市值": 9, "封单比": 9}


def _ak_symbol(code):
    """akshare 日K 接口需 sh/sz/bj 前缀；按代码首位判定。"""
    code = str(code).strip()
    if code.startswith("6"):          # 上交所（含 688 科创板）
        return "sh" + code
    if code.startswith(("0", "3")):   # 深交所（00/30）
        return "sz" + code
    if code.startswith(("8", "4")):   # 北交所
        return "bj" + code
    return code


def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _classify_board(broken, amp, first_seal, open_pct=None):
    """板型分类（纯展示用，不参与评分口径，不触碰红线计算定义）。

    依据当日数据直接判定：
      一字板  ：未炸板且开盘即封死（open_pct 接近 +10 涨停、振幅极小、无换手）
      厂字板  ：未炸板、低开(或平开)后拉升封板（open_pct 明显偏低、振幅较大）
      T字板   ：炸板 1 次（涨停→打开→极快拉回涨停，形似 T；回封斜率快）
      炸板回封：炸板 ≥2 次（多次开板仍回封，分歧大、换手充分）
      换手板  ：未炸板、非一字且非厂字（平/高开充分换手涨停，拉升斜率温和）
    """
    try:
        broken = int(broken or 0)
    except (TypeError, ValueError):
        broken = 0
    if broken == 0:
        # 一字板：开盘即涨停且几乎无波动
        if open_pct is not None and open_pct >= 9.5 and (amp is None or amp <= 0.5):
            return "一字板"
        # 厂字板：低开/平开（开盘位置明显偏下）后拉升封板，振幅通常较大
        if open_pct is not None and open_pct < -1.5 and (amp is None or amp >= 3.0):
            return "厂字板"
        if amp is not None and amp <= 0.5 and (open_pct is None or open_pct >= 9.5):
            return "一字板"
        return "换手板"
    if broken == 1:
        return "T字板"
    return "炸板回封"


def _recent_trade_dates(n=6):
    try:
        df = ak_cache(ak.tool_trade_date_hist_sina, ttl=43200)
        if df is None or df.empty:
            return []
        # trade_date 列是 object(datetime.date)，必须先用 to_datetime 转换，
        # 否则 .dt 访问器对 object 列抛 AttributeError（被 except 吞掉 → 返回 []）。
        dates = sorted(pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d").tolist())
        # 过滤未来占位日期：sina 交易日历常延伸到 2026-12-31 等未来，
        # 不过滤会拉到空涨停池、污染连板高度回溯（量化校准已同步过滤）。
        today = date.today().strftime("%Y%m%d")
        dates = [d for d in dates if d <= today]
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


def _daily_features(code, board_height):
    """从日K一次性取：首板/二板换手率、量比、振幅、开盘位置（补「量比/振幅缺口 / 板型判定」）。

    量比 = 当日成交量 / 前5日均量；振幅 = (最高-最低)/昨收；
    开盘位置 open_pct = (开盘 - 昨收) / 昨收，用于区分厂字板（低开拉升封板）。
    非交易时段日K仍可用（收盘后运行），故不再依赖盘口 spot。
    返回 (t1, t2, vr, amp, open_pct)，任一不可得为 None。
    """
    try:
        sym = _ak_symbol(code)
        df = ak_cache(ak.stock_zh_a_daily, symbol=sym, adjust="qfq", ttl=1800)
        if df is None or df.empty:
            return None, None, None, None, None
        if "换手率" in df.columns:
            vals = df["换手率"].dropna().tolist()
        else:
            vals = []
        t1 = t2 = None
        if len(vals) >= 2:
            idx1 = -(min(board_height, len(vals)))
            t1 = vals[idx1]            # 首板日换手率
            t2 = vals[-2]             # 昨日换手率（二板日）
        # 量比 / 振幅 / 开盘位置
        vr = amp = open_pct = None
        vol = df.get("volume")
        if vol is not None and len(vol) >= 6:
            v = vol.astype(float).values
            vr = float(v[-1] / v[-6:-1].mean()) if v[-6:-1].mean() else None
        hi, lo, cl, op = df.get("high"), df.get("low"), df.get("close"), df.get("open")
        if hi is not None and lo is not None and cl is not None and len(cl) >= 2:
            h, l, pc = float(hi.values[-1]), float(lo.values[-1]), float(cl.values[-2])
            amp = (h - l) / pc * 100.0 if pc else None
            if op is not None and pc:
                open_pct = (float(op.values[-1]) - pc) / pc * 100.0
        return t1, t2, vr, amp, open_pct
    except Exception:
        return None, None, None, None, None


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
    calib_weights = _load_calibration_weights()   # 无 calibrated 权重则回退默认
    calib_full = _load_calibration()              # 完整校准（贝叶斯/Platt 用）
    rows = []
    for code, r in today_pool.items():
        bh = _board_height(code, dt, dates, pools)
        t1, t2, vr, amp, open_pct = _daily_features(code, bh)
        # 单位修正：akshare 流通市值=元 → 亿元；封板资金=元 → 万元（原「封单量」列不存在）
        raw_mv = _to_float(r.get("流通市值"))            # 元
        float_mv = raw_mv / 1e8 if raw_mv is not None else None   # → 亿元
        raw_seal = _to_float(r.get("封板资金"))           # 元（封单金额）
        seal_amount_wan = raw_seal / 1e4 if raw_seal is not None else None  # → 万元
        seal_time = r.get("最后封板时间") or r.get("封板时间")   # HHMMSS
        first_seal = r.get("首次封板时间") or r.get("封板时间")  # HHMMSS
        price = _to_float(r.get("最新价"))                 # 元/股
        broken = _to_float(r.get("炸板次数")) or 0         # 炸板次数（整数）
        # 封单手数（单数）= 封板资金(元) / (最新价(元/股) × 100股/手)
        seal_orders = (raw_seal / (price * 100.0)) if (raw_seal and price) else None
        # 板型（展示用，不改评分口径）
        board_type = _classify_board(broken, amp, first_seal, open_pct)
        reason = r.get("原因") or ""
        sectors = [s.strip() for s in str(reason).replace("+", ",").split(",") if s.strip()][:3]

        feat = dict(board_height=bh, turnover_1=t1, turnover_2=t2,
                    volume_ratio=vr, amplitude=amp, seal_time=seal_time,
                    seal_amount=seal_amount_wan, float_mv=float_mv, sectors=sectors)
        ev = evaluate_limit_up(feat, weights=calib_weights)
        # 校准概率：贝叶斯 posterior（主）+ Platt（辅）
        proxy = _proxy_score(ev["items"], _PLATT_WMAP) if calib_full else None
        cal = calibrated_probability(feat, calib_full, proxy) if calib_full else None
        rows.append({
            "code": code, "name": r.get("名称"), "board_height": bh,
            "turnover_1": t1, "turnover_2": t2, "volume_ratio": vr,
            "amplitude": amp, "seal_time": seal_time, "first_seal_time": first_seal,
            "seal_amount": seal_amount_wan, "float_mv": float_mv,
            "broken_times": broken, "price": price,
            "board_type": board_type, "seal_orders": seal_orders,
            "score": ev["score"], "stage": ev["stage"],
            "sectors": sectors, "rationale": ev["rationale"], "items": ev["items"],
            "calibrated_prob": cal["prob"] if cal else None,
            "calibrated_p_cal": cal["p_cal"] if cal else None,
            "calibrated_verdict": cal["verdict"] if cal else None,
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
    # 事件戳：连板数据写入 reports 表的 created_at（写入时刻），用于前端判断新鲜度
    created_at = None
    try:
        from ..reports.store import _conn as _c2
        con2 = _c2(None)
        try:
            rr = con2.execute(
                "SELECT created_at FROM reports WHERE rtype='limit_up' AND date=? ORDER BY created_at DESC LIMIT 1",
                (row["date"],),
            ).fetchone()
            if rr:
                created_at = rr["created_at"]
        finally:
            con2.close()
    except Exception:
        pass
    return json.dumps({"ok": True, "date": row["date"], "created_at": created_at,
                       "count": len(stocks), "stocks": stocks}, ensure_ascii=False)


@mcp.tool(
    title="连板评分实证校准",
    description="拉真实涨停池(最近N交易日)构造「次日连板延续」标签，逐因子算AUC/分组成功率，"
                "输出数据驱动权重；结果写 data/score_calibration.json(供 limit_up_scan 自动采用)"
                "并落 reports.db(rtype=score_calibration)做回溯。需联网，较重，建议收盘后跑。",
)
def limit_up_calibrate(days: int = 40):
    from ..reports.score_calibrate import _collect_labeled, calibrate
    try:
        rows = _collect_labeled(days)
    except Exception as e:
        return json.dumps({"ok": False, "reason": f"校准数据采集失败: {e}"}, ensure_ascii=False)
    if not rows:
        return json.dumps({"ok": False,
                           "reason": "无样本（联网失败或非交易数据缺失），请收盘后重试"},
                          ensure_ascii=False)
    rep = calibrate(rows)
    # 落盘 JSON（供 limit_up_scan 自动加载校准权重）
    os.makedirs(os.path.dirname(_CALIB_PATH) or ".", exist_ok=True)
    with open(_CALIB_PATH, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    # 落库（reports.db，回溯；前端可展示最新校准）
    save_report("score_calibration", date.today().isoformat(), rep)
    return json.dumps({"ok": True, **rep}, ensure_ascii=False)


@mcp.tool(
    title="连板评分校准-最新",
    description="返回 reports.db 中最新一份实证校准结果（推荐权重/因子AUC/基准率/样本量），前端看板展示用。",
)
def limit_up_calibration_latest():
    r = get_latest("score_calibration")
    if r is not None:
        return json.dumps({"ok": True, "date": r["date"], "created_at": r.get("created_at"),
                           "source": "reports_db", "payload": r["payload"]}, ensure_ascii=False)
    # 回退：reports.db 无校准记录时，读 data/score_calibration.json（量化已实跑的默认校准），
    # 保证前端看板在 limit_up_calibrate 跑过之前也能展示真实校准结果。
    try:
        if os.path.exists(_CALIB_PATH):
            with open(_CALIB_PATH, encoding="utf-8") as f:
                rep = json.load(f)
            return json.dumps({"ok": True, "date": None, "source": "file_default",
                               "note": "reports.db 暂无校准记录，展示 data/score_calibration.json 默认校准",
                               "payload": rep}, ensure_ascii=False)
    except Exception:
        pass
    return json.dumps({"ok": True, "date": None,
                       "note": "暂无校准结果，请先运行 limit_up_calibrate（或收盘后流水线）"},
                      ensure_ascii=False)
