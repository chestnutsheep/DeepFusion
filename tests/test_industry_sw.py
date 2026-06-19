"""Tests for industry_sw: constituent + quote aggregation.

TDD approach — these tests MUST pass before the implementation is written.
All external akshare calls are mocked so tests run offline and fast.
"""
from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to build realistic mock DataFrames
# ---------------------------------------------------------------------------

def _mock_constituents_df() -> pd.DataFrame:
    """Simulates ak.index_component_sw output."""
    return pd.DataFrame({
        "stock_code": ["600000", "600016", "600019", "600036", "601398"],
        "stock_name": ["浦发银行", "民生银行", "宝钢股份", "招商银行", "工商银行"],
        "weight": [5.12, 3.87, 2.15, 8.64, 12.30],
        "added_date": ["20230101", "20230101", "20230101", "20230101", "20230101"],
    })


def _mock_spot_em_df() -> pd.DataFrame:
    """Simulates ak.stock_zh_a_spot_em output (only relevant columns)."""
    return pd.DataFrame({
        "代码": ["600000", "600016", "600019", "600036", "601398",
                 "000001", "000002"],  # last 2 are NOT in constituents
        "名称": ["浦发银行", "民生银行", "宝钢股份", "招商银行", "工商银行",
                 "平安银行", "万科A"],
        "最新价": [7.25, 4.12, 6.80, 35.60, 5.48,
                   11.20, 8.50],
        "涨跌幅": [1.23, -0.48, 0.59, 2.15, -1.02,
                   0.75, -2.31],
        "涨跌额": [0.09, -0.02, 0.04, 0.75, -0.06,
                   0.08, -0.20],
        "成交量": [123456, 98765, 234567, 345678, 876543,
                   456789, 567890],
        "成交额": [89012.3, 40567.8, 159456.0, 123000.4, 480123.5,
                   511234.0, 482706.5],
        "换手率": [0.42, 0.27, 0.95, 0.88, 0.25,
                   0.63, 0.51],
        "市盈率-动态": [5.12, 4.87, 8.33, 6.45, 4.92,
                        5.67, 10.23],
        "市净率": [0.48, 0.42, 0.87, 1.12, 0.55,
                   0.72, 0.91],
    })


# ---------------------------------------------------------------------------
# Fixtures — patch akshare at the cache layer
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_ak_cache(monkeypatch):
    """Replace ak_cache so that no real network calls happen."""
    from deep_fusion.data.sources import industry_sw
    from deep_fusion import cache as cache_mod

    _orig_ak_cache = cache_mod.ak_cache

    def _fake_ak_cache(fun, *args, **kwargs):
        """Return mock data based on the akshare function name."""
        name = getattr(fun, "__name__", "")
        # Pop cache-specific kwargs so they don't confuse the real function
        kwargs.pop("ttl", None)
        kwargs.pop("ttl2", None)
        kwargs.pop("key", None)

        if name == "index_component_sw":
            return _mock_constituents_df()
        elif name == "stock_zh_a_spot_em":
            return _mock_spot_em_df()
        # Fallback: call original (should not happen in these tests)
        return _orig_ak_cache(fun, *args, **kwargs)

    monkeypatch.setattr(industry_sw, "ak_cache", _fake_ak_cache)


# ---------------------------------------------------------------------------
# Test: get_constituents (existing, regression)
# ---------------------------------------------------------------------------

class TestGetConstituents:
    """Ensure existing get_constituents still works after code changes."""

    def test_returns_df_with_expected_columns(self):
        from deep_fusion.data.sources.industry_sw import get_constituents
        df = get_constituents("801011")
        assert not df.empty
        assert "stock_code" in df.columns
        assert "stock_name" in df.columns
        assert "weight" in df.columns

    def test_strips_si_suffix(self):
        from deep_fusion.data.sources.industry_sw import get_constituents
        # Should not raise; code "801011.SI" → "801011"
        df = get_constituents("801011.SI")
        assert not df.empty


# ---------------------------------------------------------------------------
# Test: get_constituents_with_quotes (NEW — TDD)
# ---------------------------------------------------------------------------

class TestGetConstituentsWithQuotes:
    """Test the new aggregation function that joins constituents + spot quotes."""

    def test_returns_dataframe(self):
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self):
        """Must include stock_code, stock_name, weight, change_pct, price, turnover."""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        required = {"stock_code", "stock_name", "weight", "change_pct", "price"}
        assert required.issubset(set(result.columns)), f"Missing columns: {required - set(result.columns)}"

    def test_only_constituent_stocks_included(self):
        """Only stocks from the constituent list should appear (not extra spot stocks)."""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        # 5 constituents in mock, spot has 7 stocks → result should be 5
        assert len(result) == 5
        # 000001 and 000002 should NOT appear
        assert "000001" not in result["stock_code"].values
        assert "000002" not in result["stock_code"].values

    def test_change_pct_is_numeric(self):
        """change_pct must be float, not string."""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        assert pd.api.types.is_numeric_dtype(result["change_pct"])

    def test_change_pct_values_correct(self):
        """涨跌幅 must match the spot data for each stock."""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        # 招商银行 600036 → +2.15%
        row = result[result["stock_code"] == "600036"].iloc[0]
        assert abs(row["change_pct"] - 2.15) < 0.01

    def test_sorted_by_weight_desc(self):
        """Default sort: weight descending (heaviest first)."""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        weights = result["weight"].tolist()
        assert weights == sorted(weights, reverse=True)

    def test_empty_on_missing_constituents(self, monkeypatch):
        """If constituent list is empty, return empty DataFrame."""
        from deep_fusion.data.sources import industry_sw

        def _empty_cache(fun, *args, **kwargs):
            name = getattr(fun, "__name__", "")
            if name == "index_component_sw":
                return pd.DataFrame()
            return _mock_spot_em_df()

        monkeypatch.setattr(industry_sw, "ak_cache", _empty_cache)
        result = industry_sw.get_constituents_with_quotes("999999")
        assert result.empty

    def test_partial_quote_coverage(self, monkeypatch):
        """Some constituent stocks might not have spot data — they should still appear with NaN."""
        from deep_fusion.data.sources import industry_sw

        # Constituents include a stock NOT in spot data
        extra_constituent = pd.DataFrame({
            "stock_code": ["600000", "600016", "688999"],
            "stock_name": ["浦发银行", "民生银行", "无行情股"],
            "weight": [5.12, 3.87, 1.00],
            "added_date": ["20230101", "20230101", "20230101"],
        })

        def _partial_cache(fun, *args, **kwargs):
            name = getattr(fun, "__name__", "")
            kwargs.pop("ttl", None)
            kwargs.pop("ttl2", None)
            kwargs.pop("key", None)
            if name == "index_component_sw":
                return extra_constituent
            if name == "stock_zh_a_spot_em":
                return _mock_spot_em_df()
            return pd.DataFrame()

        monkeypatch.setattr(industry_sw, "ak_cache", _partial_cache)
        result = industry_sw.get_constituents_with_quotes("801011")
        # Should have 3 rows
        assert len(result) == 3
        # 688999 should have NaN change_pct
        row_688999 = result[result["stock_code"] == "688999"].iloc[0]
        assert pd.isna(row_688999["change_pct"])

    def test_cache_key_includes_industry_code(self, monkeypatch):
        """get_constituents 应使用包含行业代码的缓存 key。"""
        from deep_fusion.data.sources import industry_sw

        captured_keys = []

        def _capturing_cache(fun, *args, **kwargs):
            # 模拟修复后的 ak_cache 行为：先 pop ttl/ttl2/force/key 再拼 key
            key = kwargs.pop("key", None)
            kwargs.pop("ttl", None)
            kwargs.pop("ttl2", None)
            kwargs.pop("force", None)
            if not key:
                key = f"{fun.__name__}-{args}-{kwargs}"
            captured_keys.append(key)
            name = getattr(fun, "__name__", "")
            if name == "index_component_sw":
                return _mock_constituents_df()
            if name == "stock_zh_a_spot_em":
                return _mock_spot_em_df()
            return pd.DataFrame()

        # 直接测试 get_constituents（不经过 get_constituents_with_quotes）
        monkeypatch.setattr(industry_sw, "ak_cache", _capturing_cache)
        industry_sw.get_constituents("801011")

        # 应该有 1 个 key，且包含行业代码
        assert len(captured_keys) >= 1
        assert "801011" in captured_keys[0]


# ---------------------------------------------------------------------------
# Test: MCP tool industry_sw_constituents_detail (NEW — TDD)
# ---------------------------------------------------------------------------

class TestConstituentsDetailTool:
    """Test the MCP tool wrapper (mocked data source)."""

    def test_tool_returns_csv_string(self, monkeypatch):
        from deep_fusion.tools import industry

        # Patch the data source
        monkeypatch.setattr(
            "deep_fusion.data.sources.industry_sw.get_constituents_with_quotes",
            lambda code: _mock_constituents_df().assign(
                change_pct=[1.23, -0.48, 0.59, 2.15, -1.02],
                price=[7.25, 4.12, 6.80, 35.60, 5.48],
            ),
        )
        # Call with explicit positional args — MCP Field defaults aren't resolved
        # when calling the function directly (only via fastmcp runtime).
        result = industry.industry_sw_constituents_detail("801011", 50)
        assert isinstance(result, str)
        assert "stock_code" in result

    def test_tool_handles_empty(self, monkeypatch):
        from deep_fusion.tools import industry

        monkeypatch.setattr(
            "deep_fusion.data.sources.industry_sw.get_constituents_with_quotes",
            lambda code: pd.DataFrame(),
        )
        result = industry.industry_sw_constituents_detail("999999", 50)
        assert "暂无" in result or "不可用" in result


# ---------------------------------------------------------------------------
# Regression: existing functions untouched
# ---------------------------------------------------------------------------

class TestExistingFunctionsUntouched:
    """Verify existing industry_sw functions still work after adding new code."""

    def test_get_constituents_still_works(self):
        from deep_fusion.data.sources.industry_sw import get_constituents
        df = get_constituents("801011")
        assert not df.empty
        # Should NOT have change_pct — that's only in the new function
        assert "change_pct" not in df.columns

    def test_get_tree_importable(self):
        from deep_fusion.data.sources.industry_sw import get_tree
        # get_tree reads from SQLite which may be empty — just ensure importable
        assert callable(get_tree)
