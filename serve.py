"""Quick serve script for the frontend."""
import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 东方财富(_em)和国外数据源通过 proxy:7897
# 国内数据源(申万/同花顺/新浪/雪球/巨潮/NBS)不走代理
os.environ.setdefault('HTTP_PROXY', 'http://127.0.0.1:7897')
os.environ.setdefault('HTTPS_PROXY', 'http://127.0.0.1:7897')
os.environ.setdefault('NO_PROXY',
    'swsresearch.com,'
    '10jqka.com.cn,'
    'sina.com.cn,'
    'xueqiu.com,'
    'cninfo.com.cn,'
    'stats.gov.cn,'
    'data.stats.gov.cn,'
    'localhost,127.0.0.1')

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from deep_fusion import mcp, _load_tools
from deep_fusion.logging_config import configure_logging, get_logger
from deep_fusion.metrics import metrics_app

# 触发 @mcp.tool 注册（lazy import 的工具模块）
_load_tools()

configure_logging(os.getenv('DF_LOG_LEVEL', 'WARNING'))
_LOGGER = get_logger(__name__)


async def call_tool(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        result = await mcp.call_tool(body['name'], body.get('arguments', {}))
        text = ''.join(c.text for c in result.content if hasattr(c, 'text') and c.text)
        return JSONResponse({'ok': True, 'data': text, 'updatedAt': datetime.now().isoformat()})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


async def list_tools(request: Request) -> JSONResponse:
    tools = await mcp.list_tools()
    return JSONResponse({'ok': True, 'tools': [t.name for t in tools]})


app = Starlette(routes=[
    Route('/api/tools/call', call_tool, methods=['POST']),
    Route('/api/tools/list', list_tools, methods=['GET']),
    Mount('/metrics', metrics_app),
], middleware=[
    Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*']),
])


def _warmup_cycle_cache():
    """后台预热周期计算缓存，避免首次 API 请求超时"""
    import time
    time.sleep(2)  # 等 uvicorn 完全启动
    try:
        from deep_fusion.cache import CacheKey
        import json
        from deep_fusion.analysis.macro.cycles.dispatch import _compute
        for cid, ckey in [
            ("kitchin", "cycles_data_kitchin"),
            ("juglar", "cycles_data_juglar"),
            ("kuznets", "cycles_data_kuznets"),
        ]:
            try:
                _ck = CacheKey.init(ckey, ttl=604800, ttl2=2592000)
                if _ck.get() is None:
                    _, _, res = _compute(cid, limit=0)
                    _ck.set(json.dumps(res, ensure_ascii=False))
                    print(f"  ✅ 预热 {cid} ({len(res)} 期)")
                else:
                    print(f"  ✅ {cid} 已有缓存")
            except Exception as e:
                print(f"  ⚠ {cid} 预热失败: {e}")
        # 康波 — 用 data_kondratiev() 正式路径写入，保证缓存格式一致
        try:
            from deep_fusion.tools.cycles import data_kondratiev
            for m in ["pca", "wavelet", "bandpass"]:
                _ck = CacheKey.init(f"cycles_data_kondratiev_{m}_v5", ttl=604800, ttl2=2592000)
                if _ck.get() is None:
                    data_kondratiev(m)
                    print(f"  ✅ 预热 kondratiev_{m}")
                else:
                    print(f"  ✅ kondratiev_{m} 已有缓存")
        except Exception as e:
            print(f"  ⚠ kondratiev 预热失败: {e}")
        print("  缓存预热完成")
    except Exception as e:
        print(f"  ⚠ 缓存预热失败: {e}")


def _policy_collect_loop():
    """后台定期采集政策文件（启动时 + 每 6 小时）。"""
    import time
    time.sleep(5)  # 等服务完全启动
    interval = 6 * 60 * 60  # 6 小时
    while True:
        try:
            from deep_fusion.data.sources import policy as policy_collector
            print('  ⟡ 政策采集开始...')
            totals = policy_collector.collect_all(max_pages=2)
            for site, r in totals.items():
                if 'error' in r:
                    print(f'  ❌ {site}: {r["error"]}')
                else:
                    print(f'  ✅ {site}: {r["total"]} 条, 新增 {r["new"]}')
            print('  ⟡ 政策采集完成')
        except Exception as e:
            print(f'  ⚠ 政策采集失败: {e}')
        time.sleep(interval)


import uvicorn

print(f'  ⟡ Deep Fusion API → http://localhost:5173/api')
threading.Thread(target=_warmup_cycle_cache, daemon=True).start()
threading.Thread(target=_policy_collect_loop, daemon=True).start()

# 多 worker：用模块字符串传 app，uvicorn 才能 fork 多进程
# 单 worker（默认）：直接传 app 实例，避免 import 开销
workers = int(os.getenv('DF_WORKERS', '1'))
if workers > 1:
    uvicorn.run(
        "serve:app",
        host='0.0.0.0', port=5173, log_level='warning',
        workers=workers,
    )
else:
    uvicorn.run(app, host='0.0.0.0', port=5173, log_level='warning')
