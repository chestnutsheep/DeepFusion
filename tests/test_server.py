import pytest


class TestServer:
    def test_mcp_instance(self):
        from deep_fusion import mcp
        assert mcp.name == "Deep Fusion"
        assert mcp.version == "0.1.0"

    @pytest.mark.asyncio
    async def test_tools_registered(self):
        from deep_fusion import mcp
        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        required = {"search", "market_overview", "individual_info", "individual_hist",
                    "market_prices", "get_current_time", "stock_zt_pool_em",
                    "sentiment_side", "capital_tracking", "financial_indicators",
                    "financial_statements", "peer_comparison",
                    "stock_indicators_hk", "stock_indicators_us",
                    "macro_growth", "macro_cpi", "macro_pmi",
                    "crypto_prices", "crypto_composite_diagnostic",
                    "fx_rates", "fx_history",
                    "futures_prices", "fund_info", "fund_nav",
                    "pm_spot_prices", "pm_international_prices",
                    "portfolio_add", "portfolio_view",
                    "composite_stock_diagnostic", "backtest_strategy",
                    "cache_status", "cache_clear"}
        missing = required - tool_names
        assert not missing, f"Missing tools: {missing}"

    @pytest.mark.asyncio
    async def test_prompts_registered(self):
        from deep_fusion import mcp
        prompts = await mcp.list_prompts()
        names = {p.name for p in prompts}
        required = {"analyze-stock-full", "analyze-financial-quality",
                    "analyze-industry-position", "analyze-cycle-position",
                    "generate-investment-charts", "quick-health-check",
                    "full-investment-report"}
        missing = required - names
        assert not missing, f"Missing prompts: {missing}"

    @pytest.mark.asyncio
    async def test_resources_registered(self):
        from deep_fusion import mcp
        resources = await mcp.list_resources()
        uris = {str(r.uri) for r in resources}
        required = {"skill://investment/fundamental/internal-inspection",
                    "skill://investment/cycle/kitchin-cycle",
                    "skill://investment/integration/decision-framework"}
        found = required & uris
        assert len(found) >= 1, f"No required resources found in {uris}"
