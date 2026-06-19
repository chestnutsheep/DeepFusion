"""World Bank & FRED data source adapters

Uses safe_get() from shared.request — gets retry, UA rotation, and
proxy handling automatically.

Proxy strategy:
  FRED/WB (international sites) need proxy in China, don't need proxy abroad.
  akshare/NBS (domestic sites)  generally work either way.

  This adapter uses a dual-try approach:
  1. Try with current session config (proxy or not)
  2. If that fails, flip and retry (proxy→no-proxy or no-proxy→proxy)

  The session proxy is baked at init time (from serve.py env vars).
  For the flip retry, we bypass the session and use raw requests.
"""

import logging
import os
from collections import defaultdict

import numpy as np
import requests as _raw_requests

from ...shared.request import safe_get, _get_proxies

_LOGGER = logging.getLogger(__name__)


def _flip_request(url: str, timeout: int = 15) -> _raw_requests.Response | None:
    """Try the OPPOSITE of current proxy config.

    If session has proxy → try without.
    If session has no proxy → try with env proxy.
    """
    proxies = _get_proxies()
    flip_proxies = None if proxies else proxies  # will set below if no proxy

    if proxies:
        # Currently using proxy → retry WITHOUT proxy
        old_http = os.environ.pop("HTTP_PROXY", None)
        old_https = os.environ.pop("HTTPS_PROXY", None)
        _ = os.environ.pop("http_proxy", None)
        _ = os.environ.pop("https_proxy", None)
        try:
            resp = _raw_requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp
        except Exception:
            pass
        finally:
            if old_http:
                os.environ["HTTP_PROXY"] = old_http
            if old_https:
                os.environ["HTTPS_PROXY"] = old_https
    else:
        # Currently NO proxy → try WITH proxy from INTERNATIONAL_PROXY or default
        proxy_url = os.getenv("INTERNATIONAL_PROXY") or "http://127.0.0.1:7897"
        try:
            resp = _raw_requests.get(url, timeout=timeout,
                                     proxies={"http": proxy_url, "https": proxy_url})
            if resp.status_code == 200:
                return resp
        except Exception:
            pass
    return None


def fetch_wb(indicator: str, country: str = "CN") -> list[tuple[int, float]]:
    from ...cache import CacheKey
    cache = CacheKey.init(f"wb_{country}_{indicator}", ttl=86400 * 30, ttl2=86400 * 60)
    cached = cache.get()
    if cached is not None:
        return cached

    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=200"

    # Try 1: current config (session with or without proxy)
    resp = safe_get(url, timeout=15)

    # Try 2: flip proxy config
    if resp is None:
        _LOGGER.info("WB primary fetch failed (%s/%s), trying flip proxy", indicator, country)
        resp = _flip_request(url, timeout=15)

    if resp is None:
        _LOGGER.warning("World Bank fetch failed (%s/%s): no response after dual-try", indicator, country)
        return []

    try:
        data = resp.json()
        if len(data) > 1 and isinstance(data[1], list):
            vals = [(int(item['date']), float(item['value'])) for item in data[1] if item.get('value') is not None]
            vals.sort(key=lambda x: x[0])
            cache.set(vals)
            return vals
    except Exception as e:
        _LOGGER.warning("World Bank parse failed (%s/%s): %s", indicator, country, e)
    return []


_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_fred(series_id: str) -> list[tuple[str, float]]:
    from ...cache import CacheKey
    cache = CacheKey.init(f"fred_{series_id}", ttl=86400 * 30, ttl2=86400 * 60)
    cached = cache.get()
    if cached is not None:
        return cached

    url = f"{_FRED_BASE}?id={series_id}&cosd=1900-01-01&coed=2026-12-31"

    # Try 1: current config (session with or without proxy)
    resp = safe_get(url, timeout=15)

    # Try 2: flip proxy config
    if resp is None:
        _LOGGER.info("FRED primary fetch failed (%s), trying flip proxy", series_id)
        resp = _flip_request(url, timeout=15)

    if resp is None:
        _LOGGER.warning("FRED fetch failed (%s): no response after dual-try", series_id)
        return []

    try:
        lines = resp.text.strip().split("\n")
        vals: list[tuple[str, float]] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) >= 2 and parts[1]:
                try:
                    vals.append((parts[0].strip(), float(parts[1])))
                except ValueError:
                    continue
        vals.sort(key=lambda x: x[0])
        cache.set(vals)
        return vals
    except Exception as e:
        _LOGGER.warning("FRED parse failed (%s): %s", series_id, e)
    return []


def _fred_to_annual(series: list[tuple[str, float]]) -> list[tuple[int, float]]:
    by_year: dict[int, list[float]] = defaultdict(list)
    for date_str, val in series:
        year = int(date_str[:4])
        by_year[year].append(val)
    result = sorted((y, float(np.mean(vals))) for y, vals in by_year.items())
    return result
