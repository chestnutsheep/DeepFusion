import pytest


class TestStockReportsTools:
    @pytest.mark.asyncio
    async def test_all_merged_tools_registered(self):
        from deep_fusion import mcp
        tools = {t.name for t in (await mcp.list_tools())}
        merged = {"sentiment_side", "capital_tracking", "financial_indicators",
                  "financial_statements", "peer_comparison",
                  "stock_indicators_hk", "stock_indicators_us"}
        missing = merged - tools
        assert not missing, f"Missing merged tools: {missing}"

    @pytest.mark.asyncio
    async def test_old_modules_deleted(self):
        import importlib
        for mod in ["deep_fusion.tools.sentiment",
                    "deep_fusion.tools.capital_tracking",
                    "deep_fusion.tools.fin_reports"]:
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(mod)
