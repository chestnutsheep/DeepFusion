"""校准概率（贝叶斯 posterior 主 + Platt 辅）单测。

见 agents/skills/confidence-calibration/SKILL.md §C/§E 与 AGENT_BOARD.md 共识②：
代码维护侧把校准概率接到 limit_up_scan 输出。
"""
import json
import os

import pytest

from deep_fusion.reports.score import calibrated_probability

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CALIB = os.path.join(_REPO, "data", "score_calibration.json")


@pytest.fixture
def calib():
    with open(_CALIB, encoding="utf-8") as f:
        return json.load(f)


def _feat(seal_ratio, seal_min, fmv, turnover, bh=2, sectors=True):
    """构造 limit_up features；seal_ratio(%) 逆推 seal_amount(万元)。"""
    seal_amount = seal_ratio / 100.0 * fmv * 10000.0
    return {
        "board_height": bh,
        "turnover_1": turnover,
        "seal_time": f"{seal_min // 60:02d}:{seal_min % 60:02d}",
        "seal_amount": seal_amount,
        "float_mv": fmv,
        "sectors": ["半导体"] if sectors else [],
    }


def test_prob_in_range_and_ordered(calib):
    strong = _feat(seal_ratio=2.5, seal_min=540, fmv=50, turnover=7, bh=3)
    weak = _feat(seal_ratio=0.2, seal_min=900, fmv=400, turnover=20, bh=1, sectors=False)
    p_s = calibrated_probability(strong, calib)["prob"]
    p_w = calibrated_probability(weak, calib)["prob"]
    for p in (p_s, p_w):
        assert p is not None
        assert 0.0 <= p <= 1.0
    assert p_s > p_w


def test_no_calib_returns_none():
    assert calibrated_probability(_feat(1, 600, 100, 10), None)["prob"] is None


def test_platt_cross_check(calib):
    hi = calibrated_probability(_feat(2.5, 540, 50, 7, bh=3), calib, proxy_score=90)
    lo = calibrated_probability(_feat(0.2, 900, 400, 20, bh=1, sectors=False), calib, proxy_score=40)
    assert hi["p_cal"] is not None and lo["p_cal"] is not None
    assert hi["p_cal"] > lo["p_cal"]


def test_seal_ratio_direction(calib):
    a = _feat(seal_ratio=2.0, seal_min=600, fmv=100, turnover=8, bh=2)
    b = _feat(seal_ratio=0.3, seal_min=600, fmv=100, turnover=8, bh=2)
    assert calibrated_probability(a, calib)["prob"] > calibrated_probability(b, calib)["prob"]


def test_seal_time_direction(calib):
    early = _feat(seal_ratio=1.0, seal_min=540, fmv=100, turnover=8, bh=2)   # 早盘
    late = _feat(seal_ratio=1.0, seal_min=900, fmv=100, turnover=8, bh=2)    # 尾盘
    assert calibrated_probability(early, calib)["prob"] > calibrated_probability(late, calib)["prob"]


def test_posterior_recallibration_lowers_strong(calib):
    """强股 naive posterior 被同源封板强度重复计数放大，posterior_fit 再校准须压回。

    验收点（AGENT_BOARD.md 第155-183行）：强股 naive≈0.78 → recalib≈0.55–0.66，
    且 recalib < naive；普通股(≈0.15)基本不变。
    """
    strong = _feat(seal_ratio=2.5, seal_min=540, fmv=50, turnover=7, bh=4)
    res = calibrated_probability(strong, calib)
    assert res["prob_naive"] is not None
    assert res["prob"] is not None
    assert res["prob"] < res["prob_naive"]            # 再校准压缩伪强股
    assert 0.50 <= res["prob"] <= 0.70                # 强股再校准落入合理区间
    # 普通股：naive≈0.15 再校准后基本不变
    ordinary = _feat(seal_ratio=0.3, seal_min=600, fmv=150, turnover=12, bh=2)
    r2 = calibrated_probability(ordinary, calib)
    assert abs(r2["prob"] - r2["prob_naive"]) < 0.05
