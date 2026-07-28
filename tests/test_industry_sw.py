"""Tests for industry_sw: constituent + quote aggregation.

测试铁律：
1. 正常路径必须真实调用 akshare/申万 API，不许 mock 模拟 akshare 行为
2. 异常场景（空 results、KeyError 等）允许 mock，但 mock 必须模拟 akshare 真实行为
   （抛 KeyError / 返回真实中文列名），绝不返回"已处理英文列名"
3. 真实测试请求 `_require_network` fixture，无网络时 skip

真实申万成份股 API 字段（已 curl 验证稳定）：
  stockcode / stockname / newweight / beginningdate
akshare index_component_sw rename 后的中文列名：
  证券代码 / 证券名称 / 最新权重 / 计入日期 / 序号
"""
from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers — 仅用于异常场景测试，返回 akshare 真实中文列名格式
# ---------------------------------------------------------------------------

def _real_akshare_constituents_chinese_columns() -> pd.DataFrame:
    """模拟 ak.index_component_sw 的真实中文列名输出（用于异常场景测试）。

    注意：这模拟的是 akshare **rename 后**的真实格式（中文列名），不是
    "已处理英文列名"。仅在需要隔离 akshare 网络调用、但仍要测试
    get_constituents 重命名逻辑的场景使用。
    """
    return pd.DataFrame({
        "序号": [1, 2, 3, 4, 5],
        "证券代码": ["600000", "600016", "600019", "600036", "601398"],
        "证券名称": ["浦发银行", "民生银行", "宝钢股份", "招商银行", "工商银行"],
        "最新权重": [5.12, 3.87, 2.15, 8.64, 12.30],
        "计入日期": ["2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01"],
    })


def _real_akshare_spot_em_chinese_columns() -> pd.DataFrame:
    """模拟 ak.stock_zh_a_spot_em 的真实中文列名输出（用于异常场景测试）。"""
    return pd.DataFrame({
        "代码": ["600000", "600016", "600019", "600036", "601398",
                 "000001", "000002"],
        "名称": ["浦发银行", "民生银行", "宝钢股份", "招商银行", "工商银行",
                 "平安银行", "万科A"],
        "最新价": [7.25, 4.12, 6.80, 35.60, 5.48, 11.20, 8.50],
        "涨跌幅": [1.23, -0.48, 0.59, 2.15, -1.02, 0.75, -2.31],
        "涨跌额": [0.09, -0.02, 0.04, 0.75, -0.06, 0.08, -0.20],
        "成交量": [123456, 98765, 234567, 345678, 876543, 456789, 567890],
        "成交额": [89012.3, 40567.8, 159456.0, 123000.4, 480123.5,
                   511234.0, 482706.5],
        "换手率": [0.42, 0.27, 0.95, 0.88, 0.25, 0.63, 0.51],
        "市盈率-动态": [5.12, 4.87, 8.33, 6.45, 4.92, 5.67, 10.23],
        "市净率": [0.48, 0.42, 0.87, 1.12, 0.55, 0.72, 0.91],
    })


# ---------------------------------------------------------------------------
# Test: get_constituents — 真实调用申万 API
# ---------------------------------------------------------------------------

class TestGetConstituents:
    """get_constituents 应真实调用申万 API 返回成份股。"""

    def test_returns_df_with_expected_columns(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents
        df = get_constituents("801011")
        assert not df.empty, "真实申万 API 应返回非空成份股"
        assert "stock_code" in df.columns
        assert "stock_name" in df.columns
        assert "weight" in df.columns

    def test_strips_si_suffix(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents
        # "801011.SI" → "801011"，不应抛错
        df = get_constituents("801011.SI")
        assert not df.empty

    def test_akshare_returns_chinese_columns(self, _require_network):
        """验证 ak.index_component_sw 真实返回中文列名（证明 rename 逻辑被触发）。

        这是 bug 根因的回归测试：确保 akshare 返回的就是中文列名
        （证券代码/证券名称/最新权重/计入日期），而非已处理的英文列名。
        """
        import akshare as ak
        df = ak.index_component_sw(symbol="801011")
        assert df is not None and not df.empty, "真实 akshare 应返回非空"
        # akshare rename 后的中文列名必须存在
        assert "证券代码" in df.columns
        assert "证券名称" in df.columns
        assert "最新权重" in df.columns
        assert "计入日期" in df.columns

    def test_self_fetch_handles_empty_results(self, monkeypatch):
        """_fetch_sw_constituents 在申万 API 返回空 results 时应返回空 DataFrame，不抛错。

        这是 bug 根因的直接测试：模拟申万 API 返回空 results（bug 诱因），
        验证自实现函数健壮处理，而非像 akshare 那样抛 KeyError。
        """
        from deep_fusion.data.sources import industry_sw

        class _FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"data": {"results": []}}

        class _FakeSession:
            trust_env = False
            def get(self, *args, **kwargs): return _FakeResp()

        monkeypatch.setattr("requests.Session", lambda: _FakeSession())
        df = industry_sw._fetch_sw_constituents("801011")
        assert df.empty, "空 results 应返回空 DataFrame"
        # 列必须齐全（不抛 KeyError）
        assert list(df.columns) == ["stock_code", "stock_name", "weight", "added_date"]

    def test_self_fetch_renames_fields(self, monkeypatch):
        """_fetch_sw_constituents 应将申万 API 字段重命名为英文列名。"""
        from deep_fusion.data.sources import industry_sw

        class _FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"data": {"results": [
                    {"stockcode": "600000", "stockname": "浦发银行",
                     "newweight": "5.12", "beginningdate": "2023-01-01T08:00:00+08:00"},
                ]}}

        class _FakeSession:
            trust_env = False
            def get(self, *args, **kwargs): return _FakeResp()

        monkeypatch.setattr("requests.Session", lambda: _FakeSession())
        df = industry_sw._fetch_sw_constituents("801011")
        assert len(df) == 1
        assert df.iloc[0]["stock_code"] == "600000"
        assert df.iloc[0]["stock_name"] == "浦发银行"
        assert abs(float(df.iloc[0]["weight"]) - 5.12) < 0.01
        # added_date 应是 date 对象
        assert hasattr(df.iloc[0]["added_date"], "year")

    def test_get_constituents_fallback_to_akshare(self, monkeypatch):
        """自实现失败时，get_constituents 应 fallback 到 akshare（防御 KeyError）。

        异常场景：mock _fetch_sw_constituents 返回空 + mock ak.index_component_sw
        返回真实中文列名 DataFrame，验证 fallback 分支的 rename 逻辑。
        """
        from deep_fusion.data.sources import industry_sw

        # mock ak_cache：_fetch_sw_constituents 返回空，ak.index_component_sw 返回中文列名
        def _fake_ak_cache(fun, *args, **kwargs):
            kwargs.pop("ttl", None)
            kwargs.pop("key", None)
            name = getattr(fun, "__name__", "")
            if name == "_fetch_sw_constituents":
                return pd.DataFrame(columns=["stock_code", "stock_name", "weight", "added_date"])
            if name == "index_component_sw":
                return _real_akshare_constituents_chinese_columns()
            return None

        monkeypatch.setattr(industry_sw, "ak_cache", _fake_ak_cache)
        df = industry_sw.get_constituents("801011")
        assert not df.empty
        # 验证 fallback 分支的 rename 逻辑被触发（中文→英文）
        assert "stock_code" in df.columns
        assert "stock_name" in df.columns
        assert "weight" in df.columns
        assert "added_date" in df.columns

    def test_get_constituents_returns_empty_when_both_paths_fail(self, monkeypatch):
        """自实现和 akshare 都失败时，get_constituents 应返回空 DataFrame，不崩溃。

        异常场景：模拟真实 akshare 在空 results 时抛 KeyError 的行为，
        验证 get_constituents 防御性 try/except 生效。
        """
        from deep_fusion.data.sources import industry_sw

        def _fake_ak_cache(fun, *args, **kwargs):
            kwargs.pop("ttl", None)
            kwargs.pop("key", None)
            name = getattr(fun, "__name__", "")
            if name == "_fetch_sw_constituents":
                return pd.DataFrame()  # 自实现返回空
            if name == "index_component_sw":
                # 模拟真实 akshare 在空 results 时抛 KeyError 的行为
                raise KeyError("['证券代码', '证券名称', '最新权重', '计入日期'] not in index")
            return None

        monkeypatch.setattr(industry_sw, "ak_cache", _fake_ak_cache)
        df = industry_sw.get_constituents("999999")
        assert df.empty, "两条路径都失败时应返回空 DataFrame"


# ---------------------------------------------------------------------------
# Test: get_constituents_with_quotes — 真实调用
# ---------------------------------------------------------------------------

class TestGetConstituentsWithQuotes:
    """成份股 + 行情聚合，真实调用。"""

    def test_returns_dataframe(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        required = {"stock_code", "stock_name", "weight", "change_pct", "price"}
        assert required.issubset(set(result.columns)), f"Missing: {required - set(result.columns)}"

    def test_change_pct_is_numeric(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        # 行情可用时 change_pct 应为 numeric；行情全失败时（代理/休市）可能全 NA 为 object
        non_na = result["change_pct"].dropna()
        if len(non_na) == 0:
            pytest.skip("行情数据全部不可用（代理/休市），无法验证 change_pct 类型")
        # 有非 NA 值时，列应可转为 numeric（验证不是字符串）
        pd.to_numeric(result["change_pct"], errors="raise")

    def test_sorted_by_weight_desc(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        weights = result["weight"].tolist()
        assert weights == sorted(weights, reverse=True)

    def test_empty_on_missing_constituents(self, _require_network):
        """不存在的行业代码应返回空 DataFrame，不抛错、不报 ak_cache failed。"""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("999999")
        assert result.empty

    def test_partial_quote_coverage(self, _require_network):
        """成份股在行情中无匹配时，行情字段应为 NaN（LEFT JOIN 逻辑）。"""
        from deep_fusion.data.sources.industry_sw import get_constituents_with_quotes
        result = get_constituents_with_quotes("801011")
        # 真实情况：部分股票可能停牌无行情，change_pct 可能有 NaN
        # 这里只验证 LEFT JOIN 逻辑——成份股全部出现，行情字段允许 NaN
        assert len(result) > 0
        assert "change_pct" in result.columns

    def test_cache_key_includes_industry_code(self, monkeypatch):
        """get_constituents 的缓存 key 应包含行业代码（纯逻辑测试）。

        此 mock 仅捕获 key 参数，不模拟 akshare 行为，用于验证 key 生成逻辑。
        """
        from deep_fusion.data.sources import industry_sw

        captured_keys = []

        def _capturing_cache(fun, *args, **kwargs):
            key = kwargs.pop("key", None)
            kwargs.pop("ttl", None)
            kwargs.pop("ttl2", None)
            kwargs.pop("force", None)
            if not key:
                key = f"{fun.__name__}-{args}-{kwargs}"
            captured_keys.append(key)
            # 返回空 DataFrame 让函数快速返回，不依赖网络
            return pd.DataFrame()

        monkeypatch.setattr(industry_sw, "ak_cache", _capturing_cache)
        industry_sw.get_constituents("801011")

        assert len(captured_keys) >= 1
        assert "801011" in captured_keys[0]


# ---------------------------------------------------------------------------
# Test: MCP tool industry_sw_constituents_detail
# ---------------------------------------------------------------------------

class TestConstituentsDetailTool:
    """MCP 工具层测试。"""

    def test_tool_returns_csv_string(self, _require_network):
        from deep_fusion.tools import industry
        result = industry.industry_sw_constituents_detail("801011", 50)
        assert isinstance(result, str)
        assert "stock_code" in result

    def test_tool_handles_empty(self, monkeypatch):
        """工具层空数据处理（mock 数据源函数，不模拟 akshare 行为）。"""
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
    """验证现有 industry_sw 函数仍可正常工作。"""

    def test_get_constituents_still_works(self, _require_network):
        from deep_fusion.data.sources.industry_sw import get_constituents
        df = get_constituents("801011")
        assert not df.empty
        # get_constituents 不应包含 change_pct（那是 _with_quotes 的）
        assert "change_pct" not in df.columns

    def test_get_tree_importable(self):
        from deep_fusion.data.sources.industry_sw import get_tree
        assert callable(get_tree)
