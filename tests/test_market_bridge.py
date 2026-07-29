"""market_bridge 桥接层测试（不联网，桩掉 Sina）：

验证数据契约核心：DB 优先 → 缺失回退 Sina → 拉到的原始数据写回库 → 二次读库不联网。
"""
import importlib.util
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# ── 以文件方式加载 bridge，避免触发 deep_fusion 整包 __init__ ──
_BRIDGE_PATH = Path(__file__).resolve().parents[1] / "deep_fusion" / "data" / "sources" / "market_bridge.py"


@pytest.fixture
def db_path():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(p)
    yield p
    if os.path.exists(p):
        os.remove(p)


def _load_bridge(db_path):
    os.environ["MARKET_DATA_DB_PATH"] = db_path
    spec = importlib.util.spec_from_file_location("market_bridge_test", _BRIDGE_PATH)
    mb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mb)
    return mb


# 伪 Sina 响应
_FAKE_JSON = [
    {"day": "2026-07-28", "open": "10.0", "high": "10.5", "low": "9.8", "close": "10.2", "volume": "1000"},
    {"day": "2026-07-29", "open": "10.2", "high": "10.6", "low": "10.1", "close": "10.4", "volume": "1200"},
    {"day": "2026-07-30", "open": "10.4", "high": "10.9", "low": "10.3", "close": "10.7", "volume": "900"},
]


class _FakeResp:
    def json(self):
        return list(_FAKE_JSON)


def _fake_get(*a, **k):
    return _FakeResp()


def test_db_first_then_sina_and_store(db_path, monkeypatch):
    mb = _load_bridge(db_path)
    monkeypatch.setattr(mb, "requests", type("R", (), {"get": staticmethod(_fake_get)})())

    # 第一次：库空 → 回退 Sina（桩）→ 写库
    df1 = mb.get_stock_kline("600519", days=3)
    assert len(df1) == 3
    for c in ("date", "open", "high", "low", "close", "volume"):
        assert c in df1.columns

    # 库里应有 3 行
    import sqlite3
    con = sqlite3.connect(db_path)
    n = con.execute("SELECT COUNT(*) FROM stock_daily WHERE code='600519'").fetchone()[0]
    con.close()
    assert n == 3

    # 第二次：库已存在且新鲜 → 直接读库，不再调 Sina
    calls = {"n": 0}

    def _fake_get_count(*a, **k):
        calls["n"] += 1
        return _FakeResp()

    monkeypatch.setattr(mb, "requests", type("R", (), {"get": staticmethod(_fake_get_count)})())
    df2 = mb.get_stock_kline("600519", days=3)
    assert calls["n"] == 0, "二次读取不应再联网"
    assert len(df2) == 3
    assert df2["close"].iloc[-1] == 10.7


def test_name_db_first(db_path, monkeypatch):
    mb = _load_bridge(db_path)
    # 桩 gtimg（urllib.request.urlopen）
    import urllib.request

    class _FakeU:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return "v_600519='1~贵州茅台~600519~...'".encode("gbk")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeU())
    name = mb.get_stock_name("600519")
    assert name == "贵州茅台"
    # 名称应写库
    import sqlite3
    con = sqlite3.connect(db_path)
    r = con.execute("SELECT name FROM stock_info WHERE code='600519'").fetchone()
    con.close()
    assert r is not None and r[0] == "贵州茅台"
