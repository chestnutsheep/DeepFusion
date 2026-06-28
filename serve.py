"""Quick serve script for the frontend."""
import os
import sys
import threading

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

from deep_fusion import mcp
from deep_fusion.logging_config import configure_logging, get_logger
from deep_fusion.metrics import metrics_app

configure_logging(os.getenv('DF_LOG_LEVEL', 'WARNING'))
_LOGGER = get_logger(__name__)


async def call_tool(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        result = await mcp.call_tool(body['name'], body.get('arguments', {}))
        text = ''.join(c.text for c in result.content if hasattr(c, 'text') and c.text)
        return JSONResponse({'ok': True, 'data': text})
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


import uvicorn

print(f'  ⟡ Deep Fusion API → http://localhost:5173/api')
threading.Thread(target=_warmup_cycle_cache, daemon=True).start()
uvicorn.run(app, host='0.0.0.0', port=5173, log_level='warning')
