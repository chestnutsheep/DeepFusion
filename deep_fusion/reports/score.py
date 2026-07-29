"""连板潜力股量化评分（纯函数，无网络/无副作用，便于单元测试与量化校准）。

═══════════════════════════════════════════════════════════════════════════
【数据契约 / 单位口径】—— 量化校准关键，调用方必须对齐（见 scripts/limit_up.py）
───────────────────────────────────────────────────────────────────────────
阈值与量价阶段定义来自《连板预测与大事日历》人工报告 PART 01（基于 37 只连板样本
统计）。这些是**初版启发式**，已在 score_calibrate.py 用真实连板池数据做实证校准。

features 字段与单位（与 akshare stock_zt_pool_em 对齐）：
  board_height : 连板高度（整数，来自 连板数）
  turnover_1   : 首板日换手率（%，来自 换手率）
  turnover_2   : 二板日换手率（%，来自 换手率 昨日值）
  volume_ratio : 量比（无单位；非交易时段由日K成交量推算，见 limit_up.py）
  amplitude    : 振幅（%，由日K (high-low)/prev_close 推算）
  seal_time    : 封板时间，接受 "HH:MM" / "HH:MM:SS" / "HHMMSS"（akshare 给 HHMMSS）
  seal_amount  : 封单金额，单位 **万元**（= akshare 封板资金(元) / 1e4）
  float_mv     : 流通市值，单位 **亿元**（= akshare 流通市值(元) / 1e8）
  sectors      : 题材标签列表（str）

★ 封单比 = seal_amount(万元) / float_mv(亿元) —— 两者必须同处「万 vs 亿」比例，
  score._score_seal_ratio 用 seal_amount / (float_mv*10000) 计算，单位自动抵消。
  若上游传错单位（如把 akshare 的「元」直接当「万元」），封单比会被放大/缩小 1e4 倍。
═══════════════════════════════════════════════════════════════════════════

量价四阶段（报告原文）：
  缩量蓄力 → 放量突破(首板) → 缩量加速(二板) → 分歧/出货(三板及以上)

★ 量比/振幅分阶段（"量比/振幅缺口"校准点）：原 8 项 Checklist 对量比/振幅只用单一
  黄金区间，但首板需「放量」(高量比)、二板需「缩量」(低量比)，单一区间两头不讨好。
  已改为按 board_height 分阶段打分（未知高度时回退原区间，保持兼容）。

8 项打板 Checklist 黄金区/警戒/否决（报告原文）：
  1. 换手率 turn     : 黄金 5-12% | 警戒 >20% 或 <3% | 否决 >30%
  2. 量比 vr         : 首板 黄金 1.5-3.5 / 二板 黄金 0.7-1.6 | 否决 >5(首板)/>3(二板)
  3. 二板缩量比例    : 黄金 -30%~-50% | 警戒 -10%~-30%/-50%~-70% | 否决 >+10%(放量)
  4. 封板时间        : 黄金 09:30-10:30 | 警戒 10:30-14:00 | 否决 14:00 后
  5. 振幅 amp        : 首板 黄金 6-12% / 二板 黄金 3-8% | 否决 >15%
  6. 封单/流通市值   : 黄金 >3% | 警戒 1-3% | 否决 <0.5%
  7. 题材热度        : 主线加分 / 支线减分（待量化细化主线判定）
  8. 流通市值 fmv    : 黄金 <80亿 | 警戒 80-200亿 | 否决 >500亿

权重（初版；可用 evaluate_limit_up(features, weights=...) 注入校准后权重）：
  turn20/vr12/shrink18/seal_time14/amp10/seal_ratio10/theme6/fmv10 = 100
  —— 经 score_calibrate.py 实证后，建议以「信息值(IV)归一化」重赋权（见校准报告）。
"""
import math
from datetime import datetime

# 默认权重（初版启发式，与测试契约一致）。校准后由校准脚本输出并注入。
DEFAULT_WEIGHTS = {
    "换手率": 20, "量比": 12, "二板缩量": 18, "封板时间": 14,
    "振幅": 10, "封单比": 10, "题材热度": 6, "流通市值": 10,
}


def _parse_minutes(ts):
    """封板时间 → 距零点分钟数。接受 HH:MM / HH:MM:SS / HHMMSS，解析失败返回 None。"""
    if not ts:
        return None
    s = str(ts).strip()
    if ":" in s:                       # "09:35" / "09:35:48"
        parts = s.split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return None
    digits = "".join(ch for ch in s if ch.isdigit())   # "095548" / "0955"
    if len(digits) >= 4:
        try:
            return int(digits[:2]) * 60 + int(digits[2:4])
        except Exception:
            return None
    return None


def _band(v, golden, warn_lo, warn_hi, veto):
    """区间打分：golden 区间 100；warn 区间 65；veto 返回 0；其余 40。"""
    if golden[0] <= v <= golden[1]:
        return 100
    if (warn_lo is not None and v < golden[0] and v >= warn_lo) or \
       (warn_hi is not None and v > golden[1] and v <= warn_hi):
        return 65
    if veto is not None and v > veto:
        return 0
    if veto is not None and v < veto:
        return 0
    return 40


def _score_turnover(t):
    if t is None:
        return 50, "无数据"
    if 5 <= t <= 12:
        return 100, "黄金区"
    if (3 <= t < 5) or (12 < t <= 20):
        return 65, "警戒"
    if t > 30:
        return 0, "否决(过度投机)"
    return 40, "偏弱"


def _score_volume_ratio(vr, bh=None):
    """量比分阶段：首板需放量(高量比)，二板需缩量(低量比)。bh=None 用原区间。"""
    if vr is None:
        return 50, "无数据"
    if bh is not None and bh >= 2:                      # 二板及以上：缩量加速
        if 0.7 <= vr <= 1.6:
            return 100, "黄金(缩量加速)"
        if (0.5 <= vr < 0.7) or (1.6 < vr <= 2.5):
            return 65, "警戒"
        if vr > 3:
            return 0, "否决(异常放量分歧)"
        return 40, "偏弱"
    # 首板 或 高度未知：放量突破
    if 1.5 <= vr <= 3.5:
        return 100, "黄金(放量突破)"
    if (1.0 <= vr < 1.5) or (3.5 < vr <= 5):
        return 65, "警戒"
    if vr > 5:
        return 0, "否决(异常放量)"
    return 40, "偏弱"


def _score_shrink(t1, t2):
    """二板换手率相对首板的缩量比例（负=缩量）。"""
    if t1 is None or t2 is None or t1 <= 0:
        return 50, "无对比数据"
    shrink = (t2 - t1) / t1 * 100.0
    if -50 <= shrink <= -30:
        return 100, "黄金(缩量加速)"
    if (-30 < shrink <= -10) or (-70 <= shrink < -50):
        return 65, "警戒"
    if shrink > 10:
        return 0, "否决(放量分歧)"
    if shrink < -70:
        return 40, "过度缩量(流动性枯竭)"
    return 45, "中性"


def _score_seal_time(ts):
    sec = _parse_minutes(ts)
    if sec is None:
        return 50, "无数据/解析失败"
    if sec <= 10 * 60 + 30:
        return 100, "黄金(早封板)"
    if sec <= 14 * 60:
        return 65, "警戒(午后)"
    return 30, "否决(尾盘偷板)"


def _score_amplitude(a, bh=None):
    """振幅分阶段：首板长阳(高振幅)，二板缩量小实体(低振幅)。bh=None 用原区间。"""
    if a is None:
        return 50, "无数据"
    if bh is not None and bh >= 2:                      # 二板及以上：缩量小实体
        if 3 <= a <= 8:
            return 100, "黄金(缩量小实体)"
        if (2 <= a < 3) or (8 < a <= 12):
            return 65, "警戒"
        if a > 15:
            return 0, "否决(长上影分歧)"
        return 40, "偏弱"
    # 首板 或 高度未知
    if 6 <= a <= 12:
        return 100, "黄金(放量长阳)"
    if (4 <= a < 6) or (12 < a <= 15):
        return 65, "警戒"
    if a > 15:
        return 0, "否决(长上影分歧)"
    return 40, "偏弱"


def _score_seal_ratio(seal_amount, float_mv):
    """封单金额/流通市值。seal_amount 单位万元，float_mv 单位亿元（比例自动抵消）。"""
    if not seal_amount or not float_mv:
        return 50, "无数据"
    ratio = seal_amount / (float_mv * 10000.0) * 100.0  # %
    if ratio > 3:
        return 100, "黄金(强封单)"
    if 1 <= ratio <= 3:
        return 70, "警戒"
    if ratio < 0.5:
        return 20, "否决(封单薄弱)"
    return 45, "偏弱"


def _score_theme(sectors):
    """题材热度：初版——有题材标签即给基础分，待量化细化主线判定。"""
    if sectors:
        return 70, "有题材催化"
    return 40, "无明确题材"


def _score_float_mv(fmv):
    if fmv is None:
        return 50, "无数据"
    if fmv < 80:
        return 100, "黄金(小盘弹性)"
    if fmv <= 200:
        return 70, "警戒"
    if fmv <= 500:
        return 45, "偏弱"
    return 20, "否决(大市值难连板)"


def evaluate_limit_up(features, weights=None):
    """对单只连板股评分。

    features 关键字段：board_height, turnover_1(首板换手), turnover_2(二板换手),
    volume_ratio, amplitude, seal_time, seal_amount(万元), float_mv(亿元), sectors(list)。
    weights: 可选 dict，覆盖默认权重（校准后注入）。键须与 DEFAULT_WEIGHTS 一致。
    返回 {score, grade, stage, items[], rationale}。
    """
    f = features or {}
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: v for k, v in weights.items() if k in w})

    bh = f.get("board_height")                         # None 时量比/振幅回退原区间
    items_spec = [
        ("换手率", _score_turnover(f.get("turnover_1")), w["换手率"]),
        ("量比", _score_volume_ratio(f.get("volume_ratio"), bh), w["量比"]),
        ("二板缩量", _score_shrink(f.get("turnover_1"), f.get("turnover_2")), w["二板缩量"]),
        ("封板时间", _score_seal_time(f.get("seal_time")), w["封板时间"]),
        ("振幅", _score_amplitude(f.get("amplitude"), bh), w["振幅"]),
        ("封单比", _score_seal_ratio(f.get("seal_amount"), f.get("float_mv")), w["封单比"]),
        ("题材热度", _score_theme(f.get("sectors")), w["题材热度"]),
        ("流通市值", _score_float_mv(f.get("float_mv")), w["流通市值"]),
    ]
    total = 0.0
    items = []
    for name, (sc, zone), wt in items_spec:
        total += sc * wt / 100.0
        items.append({"name": name, "score": sc, "weight": wt, "zone": zone})
    score = round(total, 1)
    if score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"

    # 阶段判定（量价四阶段）
    t1, t2 = f.get("turnover_1"), f.get("turnover_2")
    if bh is not None and bh >= 3:
        stage = "分歧/出货(高位)"
    elif bh == 2 and t1 and t2 and t2 < t1:
        stage = "缩量加速(二板)"
    elif bh == 1:
        stage = "放量突破(首板)"
    else:
        stage = "蓄力/观察"

    # rationale：取最高分与最低分项
    sorted_items = sorted(items, key=lambda x: x["score"])
    worst = sorted_items[0]
    best = sorted_items[-1]
    rationale = (f"综合评分 {score}({grade})，阶段【{stage}】。"
                 f"最强项：{best['name']}({best['zone']})；"
                 f"最弱项：{worst['name']}({worst['zone']})。")
    return {"score": score, "grade": grade, "stage": stage,
            "items": items, "rationale": rationale}


# ---------------------------------------------------------------------------
# 校准概率：贝叶斯 posterior（主）+ Platt scaling（辅）
# 见 agents/skills/confidence-calibration/SKILL.md §C / §E 与 AGENT_BOARD.md 共识。
# ---------------------------------------------------------------------------

# 无三分位边界时的回退判档（阈值对齐复跑得到的 q1/q2；top/mid/bot 对应高/中/低原始值）
_FALLBACK_TERCILE = {
    "封单比(%)": lambda v: "top_rate" if v >= 1.09 else ("mid_rate" if v >= 0.47 else "bot_rate"),
    "封板时间(分)": lambda v: "top_rate" if v >= 809 else ("mid_rate" if v >= 605 else "bot_rate"),
    "流通市值(亿)": lambda v: "top_rate" if v > 200 else ("mid_rate" if v > 80 else "bot_rate"),
    "换手率": lambda v: "top_rate" if v > 103 else ("mid_rate" if v >= 44 else "bot_rate"),
}

# 似然用到的 4 个连续因子（与 per_item_hit_rate 的键一致）
_LIKELIHOOD_FACTORS = ("封单比(%)", "封板时间(分)", "流通市值(亿)", "换手率")


def _seal_ratio_pct(features):
    """封单比(%) = 封单资金(万元) / 流通市值(亿元) / 10000 * 100。"""
    sa = features.get("seal_amount")
    fmv = features.get("float_mv")
    if not sa or not fmv:
        return None
    return sa / (fmv * 10000.0) * 100.0


def _prior_for_height(h, bh_rate, base_rate):
    """连板高度分层先验；缺失或≥6 时回退相邻可信档/总基准率。"""
    if h is None:
        return base_rate
    key = f"{float(h):.1f}"
    if key in bh_rate and bh_rate[key] is not None:
        return bh_rate[key]
    if h >= 6:
        for fb in ("5.0", "4.0"):
            if fb in bh_rate and bh_rate[fb] is not None:
                return bh_rate[fb]
    return base_rate


def _bucket_rate(info, key, val):
    """按个股真实值取该因子命中率（top/mid/bot_rate）。优先用校准边界，缺失则回退。"""
    q1, q2 = info.get("q1"), info.get("q2")
    if q1 is not None and q2 is not None:
        rate_key = "top_rate" if val >= q2 else ("mid_rate" if val >= q1 else "bot_rate")
    else:
        fb = _FALLBACK_TERCILE.get(key)
        if fb is None:
            return None
        rate_key = fb(val)
    return info.get(rate_key)


def _cal_verdict(p):
    if p is None:
        return None
    if p >= 0.50:
        return "重点"
    if p >= 0.35:
        return "可埋伏"
    if p < 0.10:
        return "不参与"
    return "观察"


def calibrated_probability(features, calib, proxy_score=None):
    """校准概率：贝叶斯 posterior（主）+ Platt p_cal（辅）。纯函数，无网络。

    features : limit_up 的 features dict（board_height/turnover_1/seal_time/
               seal_amount/float_mv/sectors）。
    calib    : data/score_calibration.json 解析 dict（含 platt_fit / per_item_hit_rate /
               board_height_rate / base_rate）。
    proxy_score : 4 因子加权代理分（供 Platt），由调用方用 recommended_weights 计算后传入。

    返回 {prob, p_cal, prior, lr, verdict}。任何必需校准项缺失时 prob=None（调用方回落到 score）。
    """
    if not calib:
        return {"prob": None, "p_cal": None, "prior": None, "lr": None, "verdict": None}
    base_rate = float(calib.get("base_rate") or 0.153)
    bh_rate = calib.get("board_height_rate") or {}
    pihr = calib.get("per_item_hit_rate") or {}

    # 1) 先验：连板高度分层 + 题材热度调节
    h = features.get("board_height")
    prior_h = _prior_for_height(h, bh_rate, base_rate)
    sector_heat = 0.7 if (features.get("sectors") or []) else 0.4  # 对齐 _score_theme 70/40
    sector_adj = 1.15 if sector_heat >= 0.6 else (0.9 if sector_heat < 0.3 else 1.0)
    prior = min(0.999, max(0.001, prior_h * sector_adj))
    prior_odds = prior / (1 - prior)

    # 2) 似然比：4 连续因子，按个股真实值判档取 hit_rate
    raw = {
        "封单比(%)": _seal_ratio_pct(features),
        "封板时间(分)": _parse_minutes(features.get("seal_time")),
        "流通市值(亿)": features.get("float_mv"),
        "换手率": features.get("turnover_1"),
    }
    lr = 1.0
    used = 0
    for key in _LIKELIHOOD_FACTORS:
        val = raw.get(key)
        if val is None:
            continue
        info = pihr.get(key)
        if not info:
            continue
        rate = _bucket_rate(info, key, val)
        if rate is None:
            continue
        lr *= rate / base_rate
        used += 1
    posterior_odds = prior_odds * lr
    posterior = posterior_odds / (1 + posterior_odds)
    posterior = min(1.0, max(0.0, posterior))

    # 3) Platt p_cal（辅助交叉校验）
    p_cal = None
    platt = calib.get("platt_fit") or {}
    if "A" in platt and "B" in platt and proxy_score is not None:
        z = platt["A"] * proxy_score + platt["B"]
        p_cal = 1.0 / (1.0 + math.exp(-z)) if -700 < z < 700 else (1.0 if z >= 0 else 0.0)

    return {
        "prob": round(posterior, 3),
        "p_cal": round(p_cal, 3) if p_cal is not None else None,
        "prior": round(prior, 3),
        "lr": round(lr, 3) if used else None,
        "verdict": _cal_verdict(posterior),
    }
