from __future__ import annotations

import atexit
import os
import pathlib
import sys
import threading
from typing import Any, ClassVar, Dict

import diskcache
from cachetools import TTLCache


class CacheKey:
    ALL: ClassVar[Dict[str, "CacheKey"]] = {}
    _init_lock: ClassVar[threading.RLock] = threading.RLock()

    key: str
    ttl: int
    ttl2: int
    cache1: TTLCache[str, Any]
    cache2: diskcache.Cache
    _cache_lock: threading.RLock

    def __init__(self, key: str, ttl: int = 600, ttl2: int | None = None, maxsize: int = 100) -> None:
        self.key = key
        self.ttl = ttl
        self.ttl2 = ttl2 or (ttl * 2)
        self.cache1 = TTLCache(maxsize=maxsize, ttl=ttl)
        self.cache2 = diskcache.Cache(self.get_cache_dir())
        self._cache_lock = threading.RLock()

    @staticmethod
    def init(key: str, ttl: int = 600, ttl2: int | None = None, maxsize: int = 100) -> "CacheKey":
        # 双重检查 + 锁，避免并发 check-then-act 创建重复实例
        existing = CacheKey.ALL.get(key)
        if existing is not None:
            return existing
        with CacheKey._init_lock:
            existing = CacheKey.ALL.get(key)
            if existing is not None:
                return existing
            cache = CacheKey(key, ttl, ttl2, maxsize)
            CacheKey.ALL[key] = cache
            return cache

    def get(self) -> Any:
        with self._cache_lock:
            try:
                val = self.cache1[self.key]
                CACHE_HITS.labels(layer="l1").inc()
                return val
            except KeyError:
                pass
            with measure_block("cache.l2_get"):
                val = self.cache2.get(self.key)
        if val is not None:
            CACHE_HITS.labels(layer="l2").inc()
        else:
            CACHE_MISSES.inc()
        return val

    def set(self, val: Any) -> Any:
        with self._cache_lock:
            self.cache1[self.key] = val
            with measure_block("cache.l2_set"):
                self.cache2.set(self.key, val, expire=self.ttl2)
        return val

    def delete(self) -> None:
        with self._cache_lock:
            self.cache1.pop(self.key, None)
            self.cache2.delete(self.key)

    def close(self) -> None:
        try:
            self.cache2.close()
        except Exception:
            pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @classmethod
    def close_all(cls) -> None:
        for obj in list(cls.ALL.values()):
            close = getattr(obj, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def get_cache_dir(self) -> pathlib.Path:
        env_dir = os.getenv("DEEP_FUSION_CACHE_DIR")
        if env_dir:
            return pathlib.Path(env_dir)
        try:
            import platformdirs
            return pathlib.Path(platformdirs.user_cache_dir("deep_fusion", ensure_exists=True))
        except ImportError:
            pass
        home = pathlib.Path.home()
        name = __package__ or "deep_fusion"
        if sys.platform == "win32":
            return home / "AppData" / "Local" / "Cache" / name
        return home / ".cache" / name


atexit.register(CacheKey.close_all)

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from unittest.mock import patch

import pandas as pd

from .metrics import (
    AKSHARE_TIMEOUT,
    CACHE_HITS,
    CACHE_MISSES,
    EVENT_LOOP_BLOCK,
    EXECUTOR_ACTIVE,
    REQUEST_LATENCY,
    measure_block,
)
from .shared.constants import REQUEST_TIMEOUT
from .logging_config import get_logger as _get_structlog

_LOGGER = logging.getLogger(__name__)
# structlog logger，用于结构化日志（含 trace_id 等字段）
_SLOG = _get_structlog(__name__)

_executor = ThreadPoolExecutor(max_workers=int(os.getenv("DF_EXECUTOR_WORKERS", "8")))

# EM (East Money) API cooldown and fallback
_last_em_error: float = 0.0
_em_lock = threading.Lock()
_EM_COOLDOWN = 60.0  # EM 限流通常以分钟计，5s 太短


def _is_em_function(fun) -> bool:
    name = getattr(fun, "__name__", "") or ""
    return name.endswith("_em")


def _has_proxy() -> bool:
    return bool(os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or
                os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"))


def _em_fallback_retry(fun, *args, **kwargs) -> pd.DataFrame | None:
    """Retry an _em call without proxy. Returns DataFrame on success, None on failure.

    用 _em_lock 串行化所有 EM fallback，避免并发下 os.environ 改写互相踩；
    用 mock.patch.dict 原子地临时移除 proxy 环境变量，异常时自动恢复。
    """
    global _last_em_error
    with _em_lock:
        now = time.time()
        if now - _last_em_error < _EM_COOLDOWN:
            _LOGGER.warning("EM cooldown active (%.1fs since last error), skipping retry",
                            now - _last_em_error)
            return None

        # 临时移除 proxy 环境变量（mock.patch.dict 保证原子恢复）
        env_override = {
            "HTTP_PROXY": None, "http_proxy": None,
            "HTTPS_PROXY": None, "https_proxy": None,
            "ALL_PROXY": None, "all_proxy": None,
        }
        try:
            _LOGGER.info("EM fallback: retrying without proxy: %s-%s", fun.__name__, args)
            with patch.dict(os.environ, env_override, clear=False):
                result = fun(*args, **kwargs)
            _last_em_error = 0.0
            _LOGGER.info("EM fallback succeeded without proxy")
            return result
        except Exception as exc2:
            _last_em_error = time.time()
            _LOGGER.error("EM fallback also failed without proxy: %s", exc2)
            return None


def ak_cache(fun, *args, **kwargs) -> pd.DataFrame | None:
    # 先 pop ttl/ttl2/force 再拼 key，避免缓存键被非业务参数污染
    key = kwargs.pop("key", None)
    force = kwargs.pop("force", False)
    ttl1 = kwargs.pop("ttl", 86400)
    ttl2 = kwargs.pop("ttl2", None)
    if not key:
        key = f"{fun.__name__}-{args}-{kwargs}"
    cache = CacheKey.init(key, ttl1, ttl2)
    all_df = cache.get()
    cache_hit = all_df is not None and not force
    if all_df is None or force:
        start = time.perf_counter()
        try:
            if _LOGGER.isEnabledFor(logging.INFO):
                _LOGGER.info("Request akshare: %s", [key, repr(args)[:200], repr(kwargs)[:200]])
            EXECUTOR_ACTIVE.inc()
            try:
                # 用 Future.result(timeout) 强制超时，避免 akshare 内部 requests 挂死
                future = _executor.submit(partial(fun, *args, **kwargs))
                try:
                    all_df = future.result(timeout=REQUEST_TIMEOUT)
                except TimeoutError:
                    AKSHARE_TIMEOUT.labels(fun=fun.__name__).inc()
                    _LOGGER.warning("ak_cache timeout after %ds: %s", REQUEST_TIMEOUT, fun.__name__)
                    _SLOG.warning("akshare_timeout", tool=fun.__name__, timeout=REQUEST_TIMEOUT)
                    all_df = None
            finally:
                EXECUTOR_ACTIVE.dec()
            if all_df is not None:
                cache.set(all_df)
        except Exception as exc:
            _LOGGER.warning("ak_cache failed: %s", exc)
            if _is_em_function(fun) and _has_proxy():
                all_df = _em_fallback_retry(fun, *args, **kwargs)
                if all_df is not None:
                    cache.set(all_df)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            REQUEST_LATENCY.labels(tool=fun.__name__).observe(elapsed_ms / 1000)
            _SLOG.info("akshare_call", tool=fun.__name__, duration_ms=round(elapsed_ms, 2),
                       cache_hit=False, key=key[:80])
    else:
        _SLOG.info("akshare_call", tool=fun.__name__, duration_ms=0.0, cache_hit=True, key=key[:80])
    return all_df


async def ak_cache_async(fun, *args, **kwargs) -> pd.DataFrame | None:
    """Async version of ak_cache that runs blocking calls in thread pool.

    cache.get/set（pickle+磁盘 I/O）也丢入 executor，彻底消除事件循环阻塞。
    akshare 调用用 asyncio.wait_for 强制超时，避免内部 requests 挂死。
    """
    # 先 pop ttl/ttl2/force 再拼 key
    key = kwargs.pop("key", None)
    force = kwargs.pop("force", False)
    ttl1 = kwargs.pop("ttl", 86400)
    ttl2 = kwargs.pop("ttl2", None)
    if not key:
        key = f"{fun.__name__}-{args}-{kwargs}"
    cache = CacheKey.init(key, ttl1, ttl2)
    loop = asyncio.get_event_loop()
    # L2 磁盘读入 executor，避免阻塞事件循环
    all_df = await loop.run_in_executor(_executor, cache.get)
    if all_df is None or force:
        start = time.perf_counter()
        try:
            if _LOGGER.isEnabledFor(logging.INFO):
                _LOGGER.info("Request akshare async: %s", [key, repr(args)[:200], repr(kwargs)[:200]])
            EXECUTOR_ACTIVE.inc()
            try:
                # asyncio.wait_for 强制超时；超时后底层线程可能仍在跑（akshare 不可中断），
                # 但事件循环不阻塞，靠 executor 容量 + EM cooldown 兜底
                try:
                    all_df = await asyncio.wait_for(
                        loop.run_in_executor(_executor, partial(fun, *args, **kwargs)),
                        timeout=REQUEST_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    AKSHARE_TIMEOUT.labels(fun=fun.__name__).inc()
                    _LOGGER.warning("ak_cache_async timeout after %ds: %s", REQUEST_TIMEOUT, fun.__name__)
                    all_df = None
            finally:
                EXECUTOR_ACTIVE.dec()
            if all_df is not None:
                # L2 磁盘写入 executor
                await loop.run_in_executor(_executor, cache.set, all_df)
        except Exception as exc:
            _LOGGER.warning("ak_cache_async failed: %s", exc)
            if _is_em_function(fun) and _has_proxy():
                EXECUTOR_ACTIVE.inc()
                try:
                    all_df = await loop.run_in_executor(
                        _executor, partial(_em_fallback_retry, fun, *args, **kwargs))
                finally:
                    EXECUTOR_ACTIVE.dec()
                if all_df is not None:
                    await loop.run_in_executor(_executor, cache.set, all_df)
        finally:
            REQUEST_LATENCY.labels(tool=fun.__name__).observe(time.perf_counter() - start)
    return all_df
