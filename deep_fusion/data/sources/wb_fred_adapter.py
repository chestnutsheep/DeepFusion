"""World Bank & FRED data source adapters"""

import logging
from collections import defaultdict

import numpy as np
import requests

_LOGGER = logging.getLogger(__name__)

def fetch_wb(indicator: str, country: str = "CN") -> list[tuple[int, float]]:
    from ...cache import CacheKey
    cache = CacheKey.init(f"wb_{country}_{indicator}", ttl=86400 * 30, ttl2=86400 * 60)
    cached = cache.get()
    if cached is not None:
        return cached
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=200"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if len(data) > 1 and isinstance(data[1], list):
            vals = [(int(item['date']), float(item['value'])) for item in data[1] if item.get('value') is not None]
            vals.sort(key=lambda x: x[0])
            cache.set(vals)
            return vals
    except Exception as e:
        _LOGGER.warning("World Bank fetch failed (%s): %s", indicator, e)
    return []

_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

def fetch_fred(series_id: str) -> list[tuple[str, float]]:
    from ...cache import CacheKey
    cache = CacheKey.init(f"fred_{series_id}", ttl=86400 * 30, ttl2=86400 * 60)
    cached = cache.get()
    if cached is not None:
        return cached
    url = f"{_FRED_BASE}?id={series_id}&cosd=1900-01-01&coed=2026-12-31"
    try:
        resp = requests.get(url, timeout=15)
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
        _LOGGER.warning("FRED fetch failed (%s): %s", series_id, e)
    return []

def _fred_to_annual(series: list[tuple[str, float]]) -> list[tuple[int, float]]:
    by_year: dict[int, list[float]] = defaultdict(list)
    for date_str, val in series:
        year = int(date_str[:4])
        by_year[year].append(val)
    result = sorted((y, float(np.mean(vals))) for y, vals in by_year.items())
    return result
