"""连板潜力股量化评分（纯函数，无网络/无副作用，便于单元测试与量化校准）。

阈值与量价阶段定义来自用户提供的《连板预测与大事日历》人工报告 PART 01
（基于 37 只连板样本统计）。这些阈值是**初版启发式**，需在"量化分析师"复核后校准。

量价四阶段（报告原文）：
  缩量蓄力 → 放量突破(首板) → 缩量加速(二板) → 分歧/出货(三板及以上)

8 项打板 Checklist 黄金区/警戒/否决（报告原文）：
  1. 换手率 turn     : 黄金 5-12% | 警戒 >20% 或 <3% | 否决 >30%
  2. 量比 vr         : 黄金 1.1-1.8 | 警戒 >3 或 <0.8 | 否决 >5
  3. 二板缩量比例    : 黄金 -30%~-50% | 警戒 -10%~-30%/-50%~-70% | 否决 >+10%(放量)
  4. 封板时间        : 黄金 09:30-10:30 | 警戒 10:30-14:00 | 否决 14:00 后
  5. 振幅 amp        : 黄金 4-8% | 警戒 8-12% 或 2-4% | 否决 >15%
  6. 封单/流通市值   : 黄金 >3% | 警戒 1-3% | 否决 <0.5%
  7. 题材热度        : 主线加分 / 支线减分（待量化细化主线判定）
  8. 流通市值 fmv    : 黄金 <80亿 | 警戒 80-200亿 | 否决 >500亿

权重（初版，待量化校准）: turn20/vr12/shrink18/seal_time14/amp10/seal_ratio10/theme6/fmv10 = 100
"""
from datetime import datetime


def _band(v, golden, warn_lo, warn_hi, veto):
    """区间打分：golden 区间 100；warn 区间 65；veto 返回 0；其余 40。"""
    if golden[0] <= v <= golden[1]:
        return 100
    if (warn_lo is not None and v < golden[0] and v >= warn_lo) or \
       (warn_hi is not None and v > golden[1] and v <= warn_hi):
        return 65
    if veto is not None and v > veto:
        return 0
    if veto is not None and v < veto:  # 下界否决（如振幅过小无意义，但此处仅上界否决用 None）
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


def _score_volume_ratio(vr):
    if vr is None:
        return 50, "无数据"
    if 1.1 <= vr <= 1.8:
        return 100, "黄金区"
    if (0.8 <= vr < 1.1) or (1.8 < vr <= 3):
        return 70, "警戒"
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
    if not ts:
        return 50, "无数据"
    try:
        hh, mm = str(ts).split(":")
        sec = int(hh) * 60 + int(mm)
    except Exception:
        return 50, "解析失败"
    if sec <= 10 * 60 + 30:
        return 100, "黄金(早封板)"
    if sec <= 14 * 60:
        return 65, "警戒(午后)"
    return 30, "否决(尾盘偷板)"


def _score_amplitude(a):
    if a is None:
        return 50, "无数据"
    if 4 <= a <= 8:
        return 100, "黄金区"
    if (2 <= a < 4) or (8 < a <= 12):
        return 65, "警戒"
    if a > 15:
        return 0, "否决(长上影分歧)"
    return 40, "偏弱"


def _score_seal_ratio(seal_amount, float_mv):
    """封单金额/流通市值。seal_amount 单位万元，float_mv 单位亿元。"""
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


def evaluate_limit_up(features):
    """对单只连板股评分。

    features 关键字段：board_height, turnover_1(首板换手), turnover_2(二板换手),
    volume_ratio, amplitude, seal_time("HH:MM"), seal_amount(万元),
    float_mv(亿元), sectors(list)。
    返回 {score, grade, stage, items[], rationale}。
    """
    f = features or {}
    items_spec = [
        ("换手率", _score_turnover(f.get("turnover_1")), 20),
        ("量比", _score_volume_ratio(f.get("volume_ratio")), 12),
        ("二板缩量", _score_shrink(f.get("turnover_1"), f.get("turnover_2")), 18),
        ("封板时间", _score_seal_time(f.get("seal_time")), 14),
        ("振幅", _score_amplitude(f.get("amplitude")), 10),
        ("封单比", _score_seal_ratio(f.get("seal_amount"), f.get("float_mv")), 10),
        ("题材热度", _score_theme(f.get("sectors")), 6),
        ("流通市值", _score_float_mv(f.get("float_mv")), 10),
    ]
    total = 0.0
    items = []
    for name, (sc, zone), w in items_spec:
        total += sc * w / 100.0
        items.append({"name": name, "score": sc, "weight": w, "zone": zone})
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
    bh = f.get("board_height") or 1
    t1, t2 = f.get("turnover_1"), f.get("turnover_2")
    if bh >= 3:
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
