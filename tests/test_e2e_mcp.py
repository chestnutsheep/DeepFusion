"""End-to-end MCP protocol test using stdio transport."""

import asyncio
import json
import sys


async def _open_proc():
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "deep_fusion",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _write_read(proc, method: str, params: dict | None = None) -> dict:
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }) + "\n"
    proc.stdin.write(req.encode())
    await proc.stdin.drain()
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=30)
    raw = line.decode("utf-8", errors="replace").strip()
    if not raw:
        raise RuntimeError("Empty response line")
    return json.loads(raw)


async def _call(method: str, params: dict | None = None) -> dict:
    proc = await _open_proc()
    try:
        resp = await _write_read(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test", "version": "1.0"},
        })
        assert "result" in resp, f"Initialize failed: {resp}"
        resp = await _write_read(proc, "notifications/initialized", {})
        return await _write_read(proc, method, params)
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass


async def test_tools_list():
    resp = await _call("tools/list")
    tools = resp["result"]["tools"]
    assert len(tools) >= 70, f"Expected ≥70 tools, got {len(tools)}"


async def test_prompts_list():
    resp = await _call("prompts/list")
    prompts = resp["result"]["prompts"]
    assert len(prompts) >= 6, f"Expected ≥6 prompts, got {len(prompts)}"


async def test_resources_list():
    resp = await _call("resources/list")
    resources = resp["result"]["resources"]
    assert len(resources) >= 10, f"Expected ≥10 resources, got {len(resources)}"


async def test_search():
    resp = await _call("tools/call", {
        "name": "search",
        "arguments": {"keyword": "久立特材"},
    })
    result = resp["result"]["content"][0]["text"]
    # CI 无代理时 EM 接口可能不可用，空结果可接受
    if "002318" not in result and "久立" not in result:
        if not result.strip() or "暂无" in result:
            return
        raise AssertionError(f"Unexpected: {result[:100]}")


async def test_industry_classify():
    resp = await _call("tools/call", {
        "name": "industry_classify",
        "arguments": {"分类标准": "申万"},
    })
    result = resp["result"]["content"][0]["text"]
    assert len(result) > 100


async def test_get_current_time():
    resp = await _call("tools/call", {
        "name": "get_current_time",
        "arguments": {},
    })
    result = resp["result"]["content"][0]["text"]
    assert "2026" in result or "2025" in result


async def test_macro_growth():
    resp = await _call("tools/call", {
        "name": "macro_growth",
        "arguments": {"limit": 3},
    })
    result = resp["result"]["content"][0]["text"]
    assert len(result) > 50


if __name__ == "__main__":
    async def main():
        for t in [
            test_tools_list, test_prompts_list, test_resources_list,
            test_search, test_industry_classify, test_get_current_time,
            test_macro_growth,
        ]:
            try:
                await t()
                print(f"  PASS  {t.__name__}")
            except Exception as e:
                print(f"  FAIL  {t.__name__}: {e}")


    asyncio.run(main())
