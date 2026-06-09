"""Check MCP text content encoding."""
import sys, asyncio
sys.path.insert(0, "/home/AI/workspace/Mcp Server/DeepFusion")
from deep_fusion import mcp

async def t():
    result = await mcp.call_tool("policy_search", {"limit": 2})
    for c in result.content:
        t = getattr(c, "text", None)
        if t:
            print(f"type: {type(t)}")
            print(f"repr: {repr(t[:100])}")
            print(f"encoded: {t.encode('utf-8')[:50]}")

asyncio.run(t())
