from dotenv import load_dotenv

load_dotenv()

import argparse
import asyncio
import importlib
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from starlette.middleware.cors import CORSMiddleware

from .server import mcp

# Tool 模块名列表（lazy import，避免顶层 import 拖慢启动）
_TOOL_MODULES = [
    "analysis", "anti_fraud", "bonds", "crypto", "cycles", "forex",
    "funds", "futures", "industry", "international", "macro", "market",
    "policy", "portfolio", "precious_metals", "spectral", "stock_reports", "stocks",
    "tech_indicators",
]

# prompts/resources 轻量，顶层 import
from . import prompts
from . import resources

_tools_loaded = False


def _load_tools():
    """延迟导入所有工具模块，触发 @mcp.tool 注册。

    在 main()/inspect 前调用，确保 MCP 协议 tools/list 能返回完整列表。
    顶层 import 时跳过，避免 import deep_fusion 本身拖慢 3-6s。
    """
    global _tools_loaded
    if _tools_loaded:
        return
    for name in _TOOL_MODULES:
        importlib.import_module(f".tools.{name}", __package__)
    _tools_loaded = True


__all__ = ["mcp", "prompts", "resources", "main"]


def _run_inspect():
    _load_tools()  # 确保 tool 已注册
    if mcp.instructions:
        print("=== Server Instructions ===")
        print(mcp.instructions)
        print("\n")

    async def _inspect():
        print("=== Registered Tools ===")
        for tool in sorted(await mcp.list_tools(), key=lambda t: t.name):
            print(f"\n{tool.name}:")
            print(f"  title: {tool.title}")
            print(f"  description: {tool.description}")

        print("\n\n=== Registered Resources ===")
        for resource in sorted(await mcp.list_resources(), key=lambda r: r.uri):
            print(f"\n{resource.uri}:")
            print(f"  name: {resource.name}")
            print(f"  description: {resource.description}")
            print(f"  mime_type: {resource.mime_type}")

        print("\n\n=== Registered Prompts ===")
        for prompt in sorted(await mcp.list_prompts(), key=lambda p: p.name):
            print(f"\n{prompt.name}:")
            print(f"  description: {prompt.description}")

    asyncio.run(_inspect())


def main():
    port = int(os.getenv("PORT", 0)) or 8000
    parser = argparse.ArgumentParser(description="Deep Fusion MCP Server")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("inspect", help="List all registered tools, resources and prompts")
    parser.add_argument("--http", action="store_true", help="Use streamable HTTP mode instead of stdio")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=port, help=f"Port to listen on (default: {port})")

    args = parser.parse_args()

    # 在解析参数后、执行命令前加载所有 tool（触发 @mcp.tool 注册）
    _load_tools()

    if args.command == "inspect":
        _run_inspect()
        return

    if args.http:
        from starlette.responses import Response
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def mcp_handler(request):
            body = await request.json()
            method = body.get("method", "")
            msg_id = body.get("id", "1")
            try:
                if method == "tools/list":
                    tools = await mcp.list_tools()
                    payload = {"jsonrpc": "2.0", "result": {
                        "tools": [t.model_dump(exclude={"fn", "serializer"}, mode="json") for t in tools]},
                               "id": msg_id}
                elif method == "tools/call":
                    name = body.get("params", {}).get("name", "")
                    arguments = body.get("params", {}).get("arguments", {})
                    result = await mcp.call_tool(name, arguments)
                    payload = {"jsonrpc": "2.0", "result": result.model_dump(mode="json"), "id": msg_id}
                else:
                    payload = {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"},
                               "id": msg_id}
                return Response(json.dumps(payload, ensure_ascii=False), media_type="application/json")
            except Exception as e:
                return Response(
                    json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": msg_id},
                               ensure_ascii=False), media_type="application/json", status_code=200)

        app = Starlette(routes=[Route("/mcp", mcp_handler, methods=["POST"])])
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                           allow_headers=["*"], max_age=86400)
        import uvicorn
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
