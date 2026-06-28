"""Prometheus 指标定义与埋点工具。

指标总览：
- REQUEST_LATENCY: MCP tool / akshare 调用耗时（Histogram, label: tool）
- CACHE_HITS / CACHE_MISSES: L1/L2 缓存命中计数（Counter, label: layer）
- EXECUTOR_ACTIVE: 线程池活跃任务数（Gauge）
- EVENT_LOOP_BLOCK: 同步阻塞段耗时（Histogram, label: op）
- AKSHARE_TIMEOUT: akshare 调用超时计数（Counter, label: fun）
- DCC_FIT_LATENCY: DCC-GARCH 拟合耗时（Histogram, label: stage）
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# --- 指标定义 ---

REQUEST_LATENCY = Histogram(
    "deepfusion_request_latency_seconds",
    "MCP tool / akshare 调用耗时",
    labelnames=("tool",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

CACHE_HITS = Counter(
    "deepfusion_cache_hits_total",
    "缓存命中次数",
    labelnames=("layer",),  # layer: "l1" | "l2"
)

CACHE_MISSES = Counter(
    "deepfusion_cache_misses_total",
    "缓存未命中次数",
)

EXECUTOR_ACTIVE = Gauge(
    "deepfusion_executor_active",
    "线程池活跃任务数",
)

EVENT_LOOP_BLOCK = Histogram(
    "deepfusion_event_loop_block_seconds",
    "事件循环线程同步阻塞段耗时",
    labelnames=("op",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

AKSHARE_TIMEOUT = Counter(
    "deepfusion_akshare_timeout_total",
    "akshare 调用超时次数",
    labelnames=("fun",),
)

DCC_FIT_LATENCY = Histogram(
    "deepfusion_dcc_fit_latency_seconds",
    "DCC-GARCH 拟合各阶段耗时",
    labelnames=("stage",),  # stage: "univariate" | "likelihood" | "fit"
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


# --- 埋点工具 ---

@contextmanager
def measure_block(op: str) -> Iterator[None]:
    """测量同步段耗时并记入 EVENT_LOOP_BLOCK。

    用法：
        with measure_block("cache.set"):
            cache.set(val)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        EVENT_LOOP_BLOCK.labels(op=op).observe(time.perf_counter() - start)


def observe_latency(tool: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：测量函数耗时并记入 REQUEST_LATENCY。

    支持同步与异步函数。
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    REQUEST_LATENCY.labels(tool=tool).observe(time.perf_counter() - start)
            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                REQUEST_LATENCY.labels(tool=tool).observe(time.perf_counter() - start)
        return sync_wrapper
    return decorator


@contextmanager
def executor_tracking() -> Iterator[None]:
    """跟踪线程池活跃任务数。

    用法：
        with executor_tracking():
            future = _executor.submit(fn, *args)
            return future.result()
    """
    EXECUTOR_ACTIVE.inc()
    try:
        yield
    finally:
        EXECUTOR_ACTIVE.dec()


# --- ASGI app for Starlette/FastAPI ---

metrics_app = make_asgi_app()
