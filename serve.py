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
from deep_fusion.logging_config import configure_logging, get_logger, RUNTIME_LOG
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


async def get_logs(request: Request) -> JSONResponse:
    """返回 runtime.log 尾部，供前端调试抽屉查看运行时 info/warn/error。

    query: ?lines=200 (默认 200, 上限 2000) & ?level=WARNING (可选过滤级别)
    """
    try:
        n = min(int(request.query_params.get('lines', 200)), 2000)
        min_level = (request.query_params.get('level') or '').upper()
        if not RUNTIME_LOG.exists():
            return JSONResponse({'ok': True, 'lines': [], 'path': str(RUNTIME_LOG)})
        out = []
        with open(RUNTIME_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line:
                    continue
                if min_level:
                    # JSON 行含 "level": "WARNING" 字段，做前缀匹配
                    if f'"level": "{min_level}"' not in line and \
                       f'"level":"{min_level}"' not in line:
                        continue
                out.append(line)
        return JSONResponse({'ok': True, 'lines': out[-n:], 'path': str(RUNTIME_LOG)})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


app = Starlette(routes=[
    Route('/api/tools/call', call_tool, methods=['POST']),
    Route('/api/tools/list', list_tools, methods=['GET']),
    Route('/api/logs', get_logs, methods=['GET']),
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
            ("kitchin", "cycles_data_kitchin_v2"),
            ("juglar", "cycles_data_juglar_v2"),
            ("kuznets", "cycles_data_kuznets_v2"),
        ]:
            try:
                _ck = CacheKey.init(ckey, ttl=604800, ttl2=2592000)
                if _ck.get() is None:
                    _, _, res = _compute(cid, limit=0)
                    _ck.set(json.dumps(res, ensure_ascii=False))
                    _LOGGER.info("warmup_done", cycle=cid, periods=len(res))
                else:
                    _LOGGER.info("warmup_cached", cycle=cid)
            except Exception as e:
                _LOGGER.warning("warmup_failed", cycle=cid, error=str(e))
        # 康波 — 用 data_kondratiev() 正式路径写入，保证缓存格式一致
        try:
            from deep_fusion.tools.cycles import data_kondratiev
            for m in ["pca", "wavelet", "bandpass"]:
                _ck = CacheKey.init(f"cycles_data_kondratiev_{m}_v5", ttl=604800, ttl2=2592000)
                if _ck.get() is None:
                    data_kondratiev(m)
                    _LOGGER.info("warmup_done", cycle=f"kondratiev_{m}")
                else:
                    _LOGGER.info("warmup_cached", cycle=f"kondratiev_{m}")
        except Exception as e:
            _LOGGER.warning("warmup_failed", cycle="kondratiev", error=str(e))
        _LOGGER.info("warmup_complete")
    except Exception as e:
        _LOGGER.warning("warmup_failed", cycle="all", error=str(e))


def _policy_collect_loop():
    """后台定期采集政策文件（启动时 + 每 6 小时）。"""
    import time
    time.sleep(5)  # 等服务完全启动
    interval = 6 * 60 * 60  # 6 小时
    while True:
        try:
            from deep_fusion.data.sources import policy as policy_collector
            _LOGGER.info("policy_collect_start")
            totals = policy_collector.collect_all(max_pages=2)
            for site, r in totals.items():
                if 'error' in r:
                    _LOGGER.error("policy_collect_error", site=site, error=r["error"])
                else:
                    _LOGGER.info("policy_collect_done", site=site, total=r["total"], new=r["new"])
            _LOGGER.info("policy_collect_complete")
        except Exception as e:
            _LOGGER.warning("policy_collect_failed", error=str(e))
        time.sleep(interval)


import uvicorn

_LOGGER.info("server_start", url="http://localhost:5173/api")
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
