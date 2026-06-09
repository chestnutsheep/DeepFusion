import pytest


class TestStocksTools:
    @pytest.mark.asyncio
    async def test_search_tool_exists(self):
        from deep_fusion import mcp
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "search" in names

    @pytest.mark.asyncio
    async def test_market_overview_tool_exists(self):
        from deep_fusion import mcp
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "market_overview" in names

    @pytest.mark.asyncio
    async def test_individual_info_tool_exists(self):
        from deep_fusion import mcp
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "individual_info" in names

    @pytest.mark.asyncio
    async def test_individual_hist_tool_exists(self):
        from deep_fusion import mcp
        tools = {t.name for t in (await mcp.list_tools())}
        assert "individual_hist" in tools

    @pytest.mark.asyncio
    async def test_market_prices_tool_exists(self):
        from deep_fusion import mcp
        tools = {t.name for t in (await mcp.list_tools())}
        assert "market_prices" in tools
