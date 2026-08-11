"""Quick serve script for the frontend."""
import os
import sys
import threading
import warnings
from datetime import datetime, date

# 抑制 websockets 14+/uvicorn 0.46 的 legacy 弃用警告（不影响功能）
# 注：实际生效点在 deep_fusion/logging_config.py（其 simplefilter("default") 会清空早期 filter）
warnings.filterwarnings(
    "ignore",
    message=r"websockets\.legacy is deprecated",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"websockets\.server\.WebSocketServerProtocol is deprecated",
    category=DeprecationWarning,
)

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


def _daily_data_collect_loop():
    """后台每日数据采集：行业日线 + 行业全景(资金流/估值/快照) + 行情增量。

    采集策略：
    - 启动后延迟 15s 先跑一次补采
    - 之后每天 16:30（收盘后）自动跑
    - 仅交易日有意义；非交易日接口返回空也不崩，自动跳过
    """
    import time
    time.sleep(15)  # 等服务完全启动 + warmup 完成
    while True:
        today = date.today()
        _LOGGER.info("daily_collect_start", date=str(today))

        # ── 1. 行业日线增量（OHLCV，约90行业）──
        try:
            from deep_fusion.tools.industry import industry_daily_collect as _idl
            _LOGGER.info("daily_collect_industry_daily_start")
            r1 = _idl(force=False)  # 增量模式：DB已最新则跳过
            _LOGGER.info("daily_collect_industry_daily_done", result=str(r1)[:200])
        except Exception as e:
            _LOGGER.warning("daily_collect_industry_daily_failed", error=str(e)[:120])

        # ── 2. 行业全景采集（资金流 + 估值 + 行情快照 + 申万分级）──
        try:
            from deep_fusion.tools.industry import industry_collect as _ic
            _LOGGER.info("daily_collect_industry_full_start")
            r2 = _ic()
            _LOGGER.info("daily_collect_industry_full_done", result=str(r2)[:300])
        except Exception as e:
            _LOGGER.warning("daily_collect_industry_full_failed", error=str(e)[:120])

        # ── 3. 行情数据增量（个股日线+指数日线）──
        try:
            from deep_fusion.data.sources.market_collector import (
                collect_stock_daily, collect_index_daily, all_stock_codes,
            )
            _LOGGER.info("daily_collect_market_start")
            # 个股增量（取最近5日，DB已最新则跳过）；codes 必填，取库内全部股票
            codes = all_stock_codes()
            r3a = collect_stock_daily(codes=codes, days_back=5)
            # 指数日线增量
            r3b = collect_index_daily(days_back=5)
            _LOGGER.info("daily_collect_market_done",
                         stock=str(r3a)[:150], index=str(r3b)[:150])
        except Exception as e:
            _LOGGER.warning("daily_collect_market_failed", error=str(e)[:120])

        # ── 4. M2/PPI/CPI 宏观指标：依赖 warmup 周期预热自动增量刷新 ──
        # warmup 调用 cycle_collect() → IndicatorDef.fetch() 走 data_lake-first + 增量更新
        # 此处不重复触网，避免双层缓存冲突

        _LOGGER.info("daily_collect_complete")

        # 算到下一个 16:30 的秒数
        now = datetime.now()
        next_run = now.replace(hour=16, minute=30, second=0, microsecond=0)
        if now >= next_run:
            next_run += datetime.timedelta(days=1)
        wait_sec = max(60, (next_run - now).total_seconds())
        _LOGGER.info("daily_collect_next", next_run=str(next_run), wait_sec=wait_sec)
        time.sleep(wait_sec)


def _daily_report_loop():
    """后台定时跑「日报类」任务并写入 reports.db（收盘后自动执行）。

    本仓库可真实自包含生成的两类：
    1) 连板潜力股：limit_up_calibrate（低频，周一跑）+ limit_up_scan（每个交易日），
       结果写 reports.db 的 limit_up_stocks 表 + rtype=score_calibration 回溯。
    2) 金融大事日历：scripts/calendar_collect.py（独立子进程，隔离 akshare 线程泄漏），
       写 reports.db 的 calendar_events 表。

    说明（非本仓库自包含，保持外部写入或后续搬入）：
    - 4 类文本日报（premarket/noonnews/qualitystock/dailyreview）生成逻辑在外部 Claw 仓库，
      通过 scripts/report_writer.py --action save_report 写入 reports 表，本循环不重复生成。
    - 热点/投资方向（invest_theme）需外部 agent 喂数据，无自动采集器，本循环不跑。

    调度：启动延迟 30s；之后锚定每个交易日 16:00（收盘后）执行，周末跳过。
    """
    import subprocess
    import time
    from datetime import datetime, date, timedelta

    time.sleep(30)  # 等 warmup / 行情采集先稳定，避免资源争抢
    REPO = os.path.dirname(os.path.abspath(__file__))
    CALENDAR_SCRIPT = os.path.join(REPO, "scripts", "calendar_collect.py")

    def _next_run_dt():
        now = datetime.now()
        nxt = now.replace(hour=16, minute=0, second=0, microsecond=0)
        if now >= nxt:
            nxt += timedelta(days=1)
        return nxt

    while True:
        today = date.today()
        weekday = today.weekday()  # 0=周一 ... 6=周日

        # 周末非交易日：跳过往后睡，避免无谓联网（节假日接口返回空也不崩，此处仅省资源）
        if weekday >= 5:
            _LOGGER.info("daily_report_skip_weekend", date=str(today))
            time.sleep(3600)
            continue

        _LOGGER.info("daily_report_start", date=str(today), weekday=weekday)

        # ── 1. 连板潜力股：每周一跑校准（重，联网），每日跑扫描 ──
        try:
            from deep_fusion.tools.limit_up import limit_up_scan, limit_up_calibrate
            if weekday == 0:  # 周一：实证校准（拉真实涨停池，较重）
                _LOGGER.info("daily_report_calibrate_start")
                try:
                    print(limit_up_calibrate(40))
                except Exception as e:
                    _LOGGER.warning("daily_report_calibrate_failed", error=str(e)[:120])
            _LOGGER.info("daily_report_limitup_start")
            print(limit_up_scan())
            _LOGGER.info("daily_report_limitup_done")
        except Exception as e:
            _LOGGER.warning("daily_report_limitup_failed", error=str(e)[:120])

        # ── 2. 金融大事日历：独立子进程跑，隔离 akshare 线程泄漏（脚本末尾 os._exit）──
        try:
            _LOGGER.info("daily_report_calendar_start")
            env = dict(os.environ)
            env.setdefault("DF_LOG_LEVEL", "WARNING")
            proc = subprocess.run(
                [sys.executable, CALENDAR_SCRIPT, "--days", "75"],
                cwd=REPO, env=env,
                capture_output=True, text=True, timeout=600,
            )
            if proc.returncode != 0:
                _LOGGER.warning("daily_report_calendar_failed",
                                rc=proc.returncode, err=proc.stderr[-300:])
            else:
                _LOGGER.info("daily_report_calendar_done", out=proc.stdout.strip()[-200:])
        except Exception as e:
            _LOGGER.warning("daily_report_calendar_failed", error=str(e)[:120])

        _LOGGER.info("daily_report_complete", date=str(today))

        # 锚定下一个交易日 16:00
        wait_sec = max(60, (datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
                            - datetime.now()).total_seconds())
        if datetime.now().hour >= 16:
            # 已错过今天 16:00：睡到明天 16:00（下个循环周末会再跳）
            nxt = _next_run_dt()
            wait_sec = max(60, (nxt - datetime.now()).total_seconds())
        _LOGGER.info("daily_report_next", wait_sec=wait_sec)
        time.sleep(wait_sec)


import uvicorn

_LOGGER.info("server_start", url="http://localhost:5173/api")
threading.Thread(target=_warmup_cycle_cache, daemon=True).start()
threading.Thread(target=_policy_collect_loop, daemon=True).start()
threading.Thread(target=_daily_data_collect_loop, daemon=True).start()
threading.Thread(target=_daily_report_loop, daemon=True).start()

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
