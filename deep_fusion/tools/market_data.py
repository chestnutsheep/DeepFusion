"""market_data.py — 公共行情 SQL 的 MCP 入口。

上层任务/前端应只读 market_data.db（详见 docs/data_contract.md）。本模块提供：
- market_data_refresh：触发联网补齐（唯一联网入口的 MCP 封装，底层 market_collector）
- market_data_query   ：从公共 SQL 读取个股/指数日 K（只读，不联网）

所有个股/指数日 K 的联网拉取只经由 market_collector，禁止各任务直连 gtimg/Sina/akshare。
"""
import asyncio
import json
from typing import Optional

from fastmcp import Context
from pydantic import Field

from ..server import mcp
from ..data.sources.market_collector import (
    DEFAULT_DB,
    collect_index_daily,
    collect_stock_daily,
    collect_stock_info,
    get_daily,
    get_index_daily,
    search_name,
)


@mcp.tool(
    title="公共行情SQL刷新",
    description=(
        "联网补齐个股/指数日 K 到公共 SQL market_data.db（唯一联网入口）。"
        "mode=full 刷指数+代码名称(轻量)；mode=stock 补指定代码；mode=index 仅指数；"
        "mode=info 仅代码名称；mode=prime 全市场当日补齐(重活，仅收盘后低峰)。"
        "所有上层任务禁止直连 gtimg/Sina/akshare 现拉 K 线，需数据先查库，缺失再调本工具。"
    ),
)
async def market_data_refresh(
    mode: str = Field(default="full", description="full/index/stock/info/prime"),
    codes: str = Field(default="", description="stock 模式的代码列表，逗号分隔"),
    days: int = Field(default=1260, description="历史深度(交易日近似)"),
    db: str = Field(default=DEFAULT_DB, description="market_data.db 路径"),
    ctx: Context | None = None,
) -> str:
    codes_list = [c.strip() for c in codes.split(",") if c.strip()]

    def _run():
        if mode == "info":
            return collect_stock_info(db_path=db)
        if mode == "index":
            return collect_index_daily(days_back=days, db_path=db)
        if mode == "full":
            return {
                "index": collect_index_daily(days_back=days, db_path=db),
                "info": collect_stock_info(db_path=db),
            }
        if mode == "stock":
            if not codes_list:
                return {"error": "stock 模式需 codes"}
            return collect_stock_daily(codes_list, days_back=days, db_path=db)
        if mode == "prime":
            from ..data.sources.market_collector import all_stock_codes

            info = collect_stock_info(db_path=db)
            all_codes = all_stock_codes(db_path=db)
            return {
                "info": info,
                "stock": collect_stock_daily(all_codes, days_back=days, db_path=db),
            }
        return {"error": f"未知 mode: {mode}"}

    if ctx:
        await ctx.report_progress(10, 100, f"开始联网补齐({mode})...")
    result = await asyncio.to_thread(_run)
    if ctx:
        await ctx.report_progress(100, 100, "补齐完成")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    title="公共行情SQL查询",
    description=(
        "从公共 SQL market_data.db 只读查询个股/指数日 K（前复权）。"
        "symbol 为6位代码查个股；加前缀如 sh000001 查指数。limit 控制返回最近条数。"
        "这是上层任务获取行情的标准只读入口，不发起网络请求。"
    ),
)
async def market_data_query(
    symbol: str = Field(description="个股6位代码，或指数代码如 sh000001"),
    limit: int = Field(default=240, description="返回最近 N 条"),
    kind: str = Field(default="auto", description="auto/stock/index"),
    db: str = Field(default=DEFAULT_DB, description="market_data.db 路径"),
    ctx: Context | None = None,
) -> str:
    def _run():
        if kind == "index" or (kind == "auto" and symbol.startswith(("sh", "sz", "bj")) and len(symbol) > 6):
            return get_index_daily(symbol, limit=limit, db_path=db)
        if symbol.startswith(("sh", "sz", "bj")) and len(symbol) == 8:
            # 形如 sh600000 的指数式写法，按个股处理（取后6位）
            return get_daily(symbol[-6:], limit=limit, db_path=db)
        return get_daily(symbol, limit=limit, db_path=db)

    result = await asyncio.to_thread(_run)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    title="公共行情SQL搜名称",
    description="在本地 stock_info 中按代码/名称模糊搜索（替代每次现拉 gtimg 名称）。",
)
async def market_data_search_name(
    keyword: str = Field(description="代码或名称关键词"),
    limit: int = Field(default=50, description="返回条数"),
    db: str = Field(default=DEFAULT_DB, description="market_data.db 路径"),
    ctx: Context | None = None,
) -> str:
    result = await asyncio.to_thread(search_name, keyword, db, limit)
    return json.dumps(result, ensure_ascii=False)
