"""RED 阶段测试：reports 存储层。

覆盖：
- reports 通用表（save/get_latest/get_history/get_by_date）
- limit_up 连板潜力股表（save/get）
- calendar_events 大事日历表（seed/upcoming/range + 动态 days_until + 埋伏窗口判定）

运行：pytest tests/test_reports_store.py -v
"""
import os
import tempfile

import pytest

from deep_fusion.reports.store import (
    init_db,
    save_report,
    get_latest,
    get_history,
    get_by_date,
    save_limit_up,
    get_limit_up,
    seed_calendar,
    add_calendar_event,
    get_calendar_upcoming,
    get_calendar_range,
)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "reports_test.db")
    init_db(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------- reports 通用表 ----------

def test_save_and_get_latest(db):
    payload = {"summary": "hello", "n": 3}
    save_report("premarket", "2026-07-29", payload, db_path=db)
    latest = get_latest("premarket", db_path=db)
    assert latest["date"] == "2026-07-29"
    assert latest["payload"]["summary"] == "hello"


def test_get_history_limit_and_order(db):
    for d in ["2026-07-27", "2026-07-28", "2026-07-29"]:
        save_report("premarket", d, {"d": d}, db_path=db)
    hist = get_history("premarket", limit=2, db_path=db)
    assert len(hist) == 2
    # 最新在前
    assert hist[0]["date"] == "2026-07-29"
    assert hist[1]["date"] == "2026-07-28"


def test_get_by_date(db):
    save_report("dailyreview", "2026-07-29", {"x": 1}, db_path=db)
    row = get_by_date("dailyreview", "2026-07-29", db_path=db)
    assert row is not None
    assert row["payload"]["x"] == 1
    assert get_by_date("dailyreview", "2026-01-01", db_path=db) is None


def test_save_report_overwrite_same_date(db):
    save_report("premarket", "2026-07-29", {"v": 1}, db_path=db)
    save_report("premarket", "2026-07-29", {"v": 2}, db_path=db)
    hist = get_history("premarket", limit=10, db_path=db)
    assert len(hist) == 1  # 同日覆盖，不重复
    assert hist[0]["payload"]["v"] == 2


# ---------- limit_up 连板潜力股表 ----------

def test_save_and_get_limit_up(db):
    rows = [
        {
            "code": "600000", "name": "浦发银行", "board_height": 2,
            "turnover_1": 9.6, "turnover_2": 5.2, "volume_ratio": 1.0,
            "amplitude": 5.1, "seal_time": "09:35", "seal_amount": 12000,
            "float_mv": 60.0, "score": 82, "stage": "缩量加速",
            "sectors": ["银行"], "rationale": "二板缩量确认",
        }
    ]
    save_limit_up("2026-07-29", rows, db_path=db)
    got = get_limit_up("2026-07-29", db_path=db)
    assert len(got) == 1
    assert got[0]["code"] == "600000"
    assert got[0]["board_height"] == 2
    assert got[0]["sectors"] == ["银行"]


def test_get_limit_up_empty(db):
    assert get_limit_up("2026-07-29", db_path=db) == []


# ---------- calendar_events 大事日历表 ----------

def test_seed_and_upcoming(db):
    events = [
        {"date": "2026-08-05", "name": "世界机器人大会", "sector": "机器人",
         "rating": 5, "category": "行业大会", "source": "manual"},
        {"date": "2026-09-03", "name": "苹果发布会", "sector": "消费电子",
         "rating": 5, "category": "行业大会", "source": "manual"},
    ]
    seed_calendar(events, db_path=db)
    # as_of = 2026-07-29，未来 14 天应只命中 8/5（距 7 天）
    upcoming = get_calendar_upcoming(days=14, as_of="2026-07-29", db_path=db)
    assert len(upcoming) == 1
    ev = upcoming[0]
    assert ev["name"] == "世界机器人大会"
    assert ev["days_until"] == 7
    assert ev["bury_window"] is True  # 7 天内 + 5 星 → 埋伏提醒


def test_upcoming_excludes_past_and_far(db):
    events = [
        {"date": "2026-07-20", "name": "已过会", "sector": "x", "rating": 5},
        {"date": "2026-12-01", "name": "太远", "sector": "x", "rating": 5},
        {"date": "2026-08-01", "name": "近期", "sector": "x", "rating": 3},
    ]
    seed_calendar(events, db_path=db)
    upcoming = get_calendar_upcoming(days=30, as_of="2026-07-29", db_path=db)
    names = [e["name"] for e in upcoming]
    assert "已过会" not in names
    assert "太远" not in names
    assert "近期" in names


def test_bury_window_only_high_rating(db):
    events = [
        {"date": "2026-08-01", "name": "低星近期", "sector": "x", "rating": 3},
    ]
    seed_calendar(events, db_path=db)
    upcoming = get_calendar_upcoming(days=30, as_of="2026-07-29", db_path=db)
    assert upcoming[0]["bury_window"] is False  # 3 星不触发埋伏提醒


def test_add_and_range(db):
    add_calendar_event("2026-08-10", "测试事件", "半导体", 4, "行业大会", db_path=db)
    rng = get_calendar_range("2026-08-01", "2026-08-31", db_path=db)
    assert len(rng) == 1
    assert rng[0]["name"] == "测试事件"
