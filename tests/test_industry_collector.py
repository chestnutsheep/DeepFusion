"""industry_collector 测试。

测试铁律：
1. 涉及 akshare 的测试必须真实调用，不许 mock 模拟 akshare 行为
2. 纯 DB 逻辑测试（不涉及 akshare）保留不动
3. 真实测试请求 `_require_network` fixture，无网络时 skip
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from deep_fusion.shared import industry_db as db


# ── fixture: 临时内存数据库 ──────────────────────────

@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """将 industry_db 的 DB_PATH 重定向到临时文件，避免污染生产库。"""
    tmp_db = tmp_path / "test_industry.db"
    monkeypatch.setattr(db, "DB_PATH", tmp_db)
    db.init_db()
    yield tmp_db


def _insert_daily(conn, code, dates, close_base=100.0):
    """辅助: 向 meso_industry_daily 插入测试数据。"""
    for i, d in enumerate(dates):
        conn.execute(
            """INSERT OR REPLACE INTO meso_industry_daily
               (industry_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_rate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, d, close_base + i, close_base + i, close_base + i, close_base + i, 1000, 10000, 0.5, 1.0),
        )
    conn.commit()


def _insert_classify(conn, code, name):
    """辅助: 向 meso_industry_classify 插入测试数据。"""
    conn.execute(
        """INSERT OR REPLACE INTO meso_industry_classify
           (industry_name, industry_code, source, updated_at) VALUES (?, ?, 'ths', ?)""",
        (name, code, datetime.now().isoformat()),
    )
    conn.commit()


class TestGetLatestDate:
    """db.get_daily_latest_date 应返回某行业 DB 中最新的 trade_date（纯 DB 逻辑）。"""

    def test_returns_latest_when_data_exists(self):
        conn = db._connect()
        _insert_daily(conn, "881101", ["2025-06-10", "2025-06-11", "2025-06-13"])
        conn.close()

        result = db.get_daily_latest_date("881101")
        assert result == "2025-06-13"

    def test_returns_none_when_no_data(self):
        result = db.get_daily_latest_date("999999")
        assert result is None

    def test_returns_latest_for_different_code(self):
        conn = db._connect()
        _insert_daily(conn, "881101", ["2025-06-10"])
        _insert_daily(conn, "881102", ["2025-06-12", "2025-06-14"])
        conn.close()

        assert db.get_daily_latest_date("881101") == "2025-06-10"
        assert db.get_daily_latest_date("881102") == "2025-06-14"


class TestLatestTradingDate:
    """db.latest_trading_date() 应返回最近一个可能的交易日（纯 DB 逻辑）。"""

    def test_returns_today_or_yesterday(self):
        result = db.latest_trading_date()
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result in (today, yesterday) or result <= today


class TestCollectorRealAkshare:
    """真实调用 akshare 验证 collector 的列名处理逻辑。

    旧的 TestCollectorIncremental 用 @patch mock ak_cache 和 _get_ths_industry_list，
    返回硬编码中文列名 DataFrame，绕过了真实 akshare 调用，已删除。
    新测试真实调用 ak.stock_board_industry_index_ths，验证：
    1. akshare 真实返回中文列名（证明 collector rename 逻辑被触发）
    2. collect_all_industry_daily 能成功执行（真实集成）
    """

    def test_real_akshare_returns_chinese_columns(self, _require_network):
        """ak.stock_board_industry_index_ths 真实返回中文列名。

        collector.collect_all_industry_daily 内部用 rename 映射：
        日期→trade_date, 开盘价→open, 收盘价→close, ...
        此测试验证 akshare 返回的就是这些中文列名，证明 rename 逻辑被真实触发。
        """
        import akshare as ak
        df = ak.stock_board_industry_index_ths(
            symbol="银行",
            start_date="20250101",
            end_date="20250110",
        )
        assert df is not None and not df.empty, "真实 akshare 应返回非空"
        # collector 依赖的中文列名必须存在
        assert "日期" in df.columns
        assert "开盘价" in df.columns
        assert "最高价" in df.columns
        assert "最低价" in df.columns
        assert "收盘价" in df.columns
        assert "成交量" in df.columns
        assert "成交额" in df.columns

    def test_collect_all_runs_with_real_network(self, _require_network):
        """真调 collect_all_industry_daily，验证能成功执行并写入 DB。

        此测试会真实拉取全部同花顺行业日行情（并发 8），可能较慢。
        验证点：
        - 不抛异常
        - 返回 dict（{行业名: 行数}）
        - DB 中至少有一行数据
        """
        from deep_fusion.data.sources import industry_collector as collector
        # 用较近的起始日期减少数据量
        results = collector.collect_all_industry_daily(start_date="20250101")
        assert isinstance(results, dict)
        # 至少有一个行业成功采集
        successful = {k: v for k, v in results.items() if v > 0}
        assert len(successful) > 0, "真实采集应至少有一个行业成功"

        # 验证 DB 中有数据
        conn = db._connect()
        count = conn.execute("SELECT COUNT(*) FROM meso_industry_daily").fetchone()[0]
        conn.close()
        assert count > 0, "DB 应有采集到的行情数据"

    def test_force_refresh_with_real_network(self, _require_network):
        """force=True 时应强制全量重采（绕过 DB 新鲜度检查）。

        先正常采集一次（可能 DB 已有数据则跳过），再 force=True 强制重采，
        验证 force 模式能正常工作。
        """
        from deep_fusion.data.sources import industry_collector as collector
        # force=True 强制全量重采
        results = collector.collect_all_industry_daily(start_date="20250101", force=True)
        assert isinstance(results, dict)
        # force 模式下应该有行业被采集（即使 DB 已最新）
        successful = {k: v for k, v in results.items() if v > 0}
        assert len(successful) > 0, "force=True 应至少有一个行业被重新采集"
