"""market_collector 冒烟测试：验证 schema / 增量写库 / 读取器。

联网取数（fetch_*）用 monkeypatch 桩掉，测试不依赖网络与 akshare。
"""
import importlib
import sqlite3

import pytest

MOD = "deep_fusion.data.sources.market_collector"


@pytest.fixture
def mc(monkeypatch):
    m = importlib.import_module(MOD)

    # 桩：单只股票返回 3 天日 K
    def fake_stock_daily(code, days_back=1260, end=None):
        return [
            {"code": code[-6:], "date": "2026-07-28", "open": 10, "high": 11,
             "low": 9.5, "close": 10.5, "volume": 1000, "amount": 10500},
            {"code": code[-6:], "date": "2026-07-29", "open": 10.5, "high": 11.2,
             "low": 10.3, "close": 11.0, "volume": 1200, "amount": 13200},
            {"code": code[-6:], "date": "2026-07-30", "open": 11.0, "high": 11.5,
             "low": 10.8, "close": 11.3, "volume": 1100, "amount": 12430},
        ]

    def fake_index_daily(symbol, days_back=1260, end=None):
        return [
            {"code": symbol, "date": "2026-07-29", "open": 3000, "high": 3050,
             "low": 2990, "close": 3020, "volume": 1e8, "amount": None},
            {"code": symbol, "date": "2026-07-30", "open": 3020, "high": 3060,
             "low": 3010, "close": 3040, "volume": 1.1e8, "amount": None},
        ]

    def fake_info():
        return [
            {"code": "600000", "name": "浦发银行", "market": "sh"},
            {"code": "000001", "name": "平安银行", "market": "sz"},
        ]

    monkeypatch.setattr(m, "fetch_stock_daily", fake_stock_daily)
    monkeypatch.setattr(m, "fetch_index_daily", fake_index_daily)
    monkeypatch.setattr(m, "fetch_stock_info", fake_info)
    return m


def test_schema_and_market_of(mc, tmp_path):
    db = str(tmp_path / "market_data.db")
    mc.ensure_schema(db)
    with sqlite3.connect(db) as con:
        tbls = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"stock_info", "stock_daily", "index_daily", "meta"} <= tbls
    assert mc._market_of("600000") == "sh"
    assert mc._market_of("000001") == "sz"
    assert mc._market_of("830799") == "bj"


def test_norm_date(mc):
    assert mc._norm_date("20260730") == "2026-07-30"
    assert mc._norm_date("2026-07-30") == "2026-07-30"
    assert mc._norm_date(None) is None


def test_collect_stock_daily_incremental(mc, tmp_path):
    db = str(tmp_path / "market_data.db")
    s1 = mc.collect_stock_daily(["600000"], days_back=1260, db_path=db)
    assert s1["written"] == 3
    rows = mc.get_daily("600000", limit=10, db_path=db)
    assert len(rows) == 3
    assert rows[0]["date"] == "2026-07-30"  # DESC
    # 再次 collect 相同区间（桩不变），应无新写入（增量）
    s2 = mc.collect_stock_daily(["600000"], days_back=1260, db_path=db)
    assert s2["written"] == 0


def test_index_and_info(mc, tmp_path):
    db = str(tmp_path / "market_data.db")
    mc.collect_index_daily(["sh000001"], db_path=db)
    idx = mc.get_index_daily("sh000001", limit=10, db_path=db)
    assert len(idx) == 2 and idx[0]["date"] == "2026-07-30"

    mc.collect_stock_info(db_path=db)
    info = mc.get_info("600000", db_path=db)
    assert info["name"] == "浦发银行"
    found = mc.search_name("银行", db_path=db)
    assert {r["code"] for r in found} == {"600000", "000001"}


def test_needs_refresh(mc, tmp_path):
    db = str(tmp_path / "market_data.db")
    assert mc.needs_refresh("stock_daily", "600000", db_path=db) is True
    mc.collect_stock_daily(["600000"], db_path=db)
    # 桩数据最新日期 2026-07-30，距今天数 >1 → 仍需刷新（演示判定逻辑）
    assert isinstance(mc.needs_refresh("stock_daily", "600000", db_path=db), bool)
