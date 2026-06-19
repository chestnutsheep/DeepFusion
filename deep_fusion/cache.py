from __future__ import annotations

import atexit
import os
import pathlib
import sys
from typing import Any, ClassVar, Dict

import diskcache
from cachetools import TTLCache


class CacheKey:
    ALL: ClassVar[Dict[str, "CacheKey"]] = {}

    key: str
    ttl: int
    ttl2: int
    cache1: TTLCache[str, Any]
    cache2: diskcache.Cache

    def __init__(self, key: str, ttl: int = 600, ttl2: int | None = None, maxsize: int = 100) -> None:
        self.key = key
        self.ttl = ttl
        self.ttl2 = ttl2 or (ttl * 2)
        self.cache1 = TTLCache(maxsize=maxsize, ttl=ttl)
        self.cache2 = diskcache.Cache(self.get_cache_dir())

    @staticmethod
    def init(key: str, ttl: int = 600, ttl2: int | None = None, maxsize: int = 100) -> "CacheKey":
        if key in CacheKey.ALL:
            return CacheKey.ALL[key]
        cache = CacheKey(key, ttl, ttl2, maxsize)
        return CacheKey.ALL.setdefault(key, cache)

    def get(self) -> Any:
        try:
            return self.cache1[self.key]
        except KeyError:
            pass
        return self.cache2.get(self.key)

    def set(self, val: Any) -> Any:
        self.cache1[self.key] = val
        self.cache2.set(self.key, val, expire=self.ttl2)
        return val

    def delete(self) -> None:
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

import pandas as pd

_LOGGER = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=8)

# EM (East Money) API cooldown and fallback
_last_em_error: float = 0.0
_EM_COOLDOWN = 5.0


def _is_em_function(fun) -> bool:
    name = getattr(fun, "__name__", "") or ""
    return name.endswith("_em")


def _has_proxy() -> bool:
    return bool(os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or
                os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"))


def _em_fallback_retry(fun, *args, **kwargs) -> pd.DataFrame | None:
    """Retry an _em call without proxy. Returns DataFrame on success, None on failure."""
    global _last_em_error
    now = time.time()
    if now - _last_em_error < _EM_COOLDOWN:
        _LOGGER.warning("EM cooldown active (%.1fs since last error), skipping retry",
                        now - _last_em_error)
        return None

    old_http = os.environ.pop("HTTP_PROXY", None)
    old_https = os.environ.pop("HTTPS_PROXY", None)
    _ = os.environ.pop("http_proxy", None)
    _ = os.environ.pop("https_proxy", None)
    try:
        _LOGGER.info("EM fallback: retrying without proxy: %s-%s", fun.__name__, args)
        result = fun(*args, **kwargs)
        _last_em_error = 0.0
        _LOGGER.info("EM fallback succeeded without proxy")
        return result
    except Exception as exc2:
        _last_em_error = time.time()
        _LOGGER.error("EM fallback also failed without proxy: %s", exc2)
        return None
    finally:
        if old_http:
            os.environ["HTTP_PROXY"] = old_http
        if old_https:
            os.environ["HTTPS_PROXY"] = old_https


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
    if all_df is None or force:
        try:
            _LOGGER.info("Request akshare: %s", [key, args, kwargs])
            all_df = fun(*args, **kwargs)
            cache.set(all_df)
        except Exception as exc:
            _LOGGER.warning("ak_cache failed: %s", exc)
            if _is_em_function(fun) and _has_proxy():
                all_df = _em_fallback_retry(fun, *args, **kwargs)
                if all_df is not None:
                    cache.set(all_df)
    return all_df


async def ak_cache_async(fun, *args, **kwargs) -> pd.DataFrame | None:
    """Async version of ak_cache that runs blocking calls in thread pool."""
    # 先 pop ttl/ttl2/force 再拼 key
    key = kwargs.pop("key", None)
    force = kwargs.pop("force", False)
    ttl1 = kwargs.pop("ttl", 86400)
    ttl2 = kwargs.pop("ttl2", None)
    if not key:
        key = f"{fun.__name__}-{args}-{kwargs}"
    cache = CacheKey.init(key, ttl1, ttl2)
    all_df = cache.get()
    if all_df is None or force:
        try:
            _LOGGER.info("Request akshare async: %s", [key, args, kwargs])
            loop = asyncio.get_event_loop()
            all_df = await loop.run_in_executor(_executor, partial(fun, *args, **kwargs))
            cache.set(all_df)
        except Exception as exc:
            _LOGGER.warning("ak_cache_async failed: %s", exc)
            if _is_em_function(fun) and _has_proxy():
                loop2 = asyncio.get_event_loop()
                all_df = await loop2.run_in_executor(
                    _executor, partial(_em_fallback_retry, fun, *args, **kwargs))
                if all_df is not None:
                    cache.set(all_df)
    return all_df
