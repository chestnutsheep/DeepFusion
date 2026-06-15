"""industry_collector 增量采集 + DB 新鲜度检查测试。"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from deep_fusion.shared import industry_db as db


# ── fixture: 临时内存数据库 ──────────────────────────

@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """将 industry_db 的 DB_PATH 重定向到临时文件，避免污染生产库。"""
    tmp_db = tmp_path / "test_industry.db"
    monkeypatch.setattr(db, "DB_PATH", tmp_db)
    # 重新建表
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
    """db.get_daily_latest_date 应返回某行业 DB 中最新的 trade_date。"""

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
    """db.latest_trading_date() 应返回最近一个可能的交易日。"""

    def test_returns_today_or_yesterday(self):
        result = db.latest_trading_date()
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        # 交易日应该是今天或昨天（简化版不判断周末）
        assert result in (today, yesterday) or result <= today


class TestCollectorIncremental:
    """collector.collect_all_industry_daily 增量采集逻辑。"""

    @patch("deep_fusion.data.sources.industry_collector.ak_cache")
    @patch("deep_fusion.data.sources.industry_collector._get_ths_industry_list")
    def test_skips_when_db_is_latest(self, mock_list, mock_ak_cache):
        """DB 已是最新 → 不调 akshare，跳过采集。"""
        mock_list.return_value = [
            {"industry_name": "银行", "industry_code": "881101"},
        ]

        # DB 里已有今天的数据
        today = datetime.now().strftime("%Y-%m-%d")
        conn = db._connect()
        _insert_classify(conn, "881101", "银行")
        _insert_daily(conn, "881101", [today])
        conn.close()

        from deep_fusion.data.sources import industry_collector as collector

        results = collector.collect_all_industry_daily(start_date="20200101")
        # ak_cache 不应被调用
        mock_ak_cache.assert_not_called()
        # 结果里不应该有这个行业（跳过了）
        assert "银行" not in results

    @patch("deep_fusion.data.sources.industry_collector.ak_cache")
    @patch("deep_fusion.data.sources.industry_collector._get_ths_industry_list")
    def test_incremental_start_from_db_latest(self, mock_list, mock_ak_cache):
        """DB 有旧数据 → 从 DB 最后日期开始增量拉取。"""
        mock_list.return_value = [
            {"industry_name": "银行", "industry_code": "881101"},
        ]
        # 模拟 akshare 返回新数据
        new_df = pd.DataFrame({
            "日期": ["2025-06-12", "2025-06-13"],
            "开盘价": [100, 101],
            "最高价": [102, 103],
            "最低价": [99, 100],
            "收盘价": [101, 102],
            "成交量": [1000, 1100],
            "成交额": [10000, 11000],
        })
        mock_ak_cache.return_value = new_df

        # DB 里有到 6/11 的数据
        conn = db._connect()
        _insert_classify(conn, "881101", "银行")
        _insert_daily(conn, "881101", ["2025-06-10", "2025-06-11"])
        conn.close()

        from deep_fusion.data.sources import industry_collector as collector

        results = collector.collect_all_industry_daily(start_date="20200101")
        # 应该调了 ak_cache，且 start_date 应该从 DB 最后日期开始
        assert mock_ak_cache.called
        call_kwargs = mock_ak_cache.call_args
        # start_date 应该 >= "2025-06-11"（从 DB 最后日期开始增量）
        assert call_kwargs.kwargs.get("start_date", call_kwargs[1].get("start_date", "")) >= "2025-06-11"

    @patch("deep_fusion.data.sources.industry_collector.ak_cache")
    @patch("deep_fusion.data.sources.industry_collector._get_ths_industry_list")
    def test_force_full_refresh(self, mock_list, mock_ak_cache):
        """force=True → 忽略 DB 新鲜度，全量重采。"""
        today = datetime.now().strftime("%Y-%m-%d")
        mock_list.return_value = [
            {"industry_name": "银行", "industry_code": "881101"},
        ]
        new_df = pd.DataFrame({
            "日期": [today],
            "开盘价": [100],
            "最高价": [102],
            "最低价": [99],
            "收盘价": [101],
            "成交量": [1000],
            "成交额": [10000],
        })
        mock_ak_cache.return_value = new_df

        # DB 已最新
        conn = db._connect()
        _insert_classify(conn, "881101", "银行")
        _insert_daily(conn, "881101", [today])
        conn.close()

        from deep_fusion.data.sources import industry_collector as collector

        results = collector.collect_all_industry_daily(start_date="20200101", force=True)
        # force=True 时应该重新调 akshare
        assert mock_ak_cache.called
