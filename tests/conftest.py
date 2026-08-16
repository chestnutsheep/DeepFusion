import pytest


@pytest.fixture(scope="session", autouse=True)
def _load_mcp_tools():
    """确保 MCP 工具在测试前完成注册。

    真实服务入口（serve.py main / deep_fusion.__init__._run_inspect）会调用
    _load_tools() 触发 @mcp.tool 注册；但测试直接 `from deep_fusion import mcp`
    时不会触发延迟加载，导致 list_tools() 返回空、工具名断言失败。
    这里在 session 级统一触发一次，对齐生产加载路径。
    """
    from deep_fusion import _load_tools

    _load_tools()
    yield


@pytest.fixture(autouse=True)
def _reset_cache_registry():
    try:
        from deep_fusion import CacheKey
    except ImportError:
        yield
        return
    saved = dict(CacheKey.ALL)
    CacheKey.ALL.clear()
    yield
    CacheKey.ALL.clear()
    CacheKey.ALL.update(saved)


@pytest.fixture(scope="session")
def _require_network():
    """真实网络可用性探测 fixture，供真实 akshare/申万 API 测试按需请求。

    用法：测试函数签名加 `_require_network` 参数即可。无网络/无法访问申万 API
    时该 fixture 触发 pytest.skip，避免真实测试在离线环境误报失败。

    注意：此 fixture **不是 autouse**，纯逻辑测试不受影响。
    """
    import requests
    import warnings
    warnings.filterwarnings("ignore")  # 抑制 InsecureRequestWarning

    try:
        # 申万是境内站点，trust_env=False 绕过代理，verify=False 跳过证书验证
        # （与 _fetch_sw_constituents 的请求方式一致）
        session = requests.Session()
        session.trust_env = False
        resp = session.get(
            "https://www.swsresearch.com",
            timeout=5,
            allow_redirects=False,
            verify=False,
        )
        # 任何 HTTP 响应（含 4xx/5xx）都说明网络可达
        if resp.status_code < 600:
            return True
    except Exception:
        pass
    pytest.skip("无网络或无法访问申万 API，跳过真实集成测试")
