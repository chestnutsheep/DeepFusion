import logging
import os
import random
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

_session: requests.Session | None = None


def _get_proxies() -> dict[str, str] | None:
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if not http_proxy and not https_proxy:
        return None
    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies or None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        proxies = _get_proxies()
        if proxies:
            _session.proxies.update(proxies)
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def _rotate_ua(session: requests.Session) -> None:
    session.headers.update({"User-Agent": random.choice(_USER_AGENTS)})


def safe_get(url: str, params: dict[str, Any] | None = None, timeout: int | None = None) -> requests.Response | None:
    session = _get_session()
    _rotate_ua(session)
    t = timeout or REQUEST_TIMEOUT
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=t)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = (attempt + 1) * 2.0 + random.uniform(0, 1)
                _LOGGER.warning("rate limited (%s), retrying in %.1fs", resp.status_code, wait)
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as exc:
            wait = (attempt + 1) * 2.0 + random.uniform(0, 1)
            _LOGGER.warning("request failed (%s), retrying in %.1fs", exc, wait)
            time.sleep(wait)
    return None


def safe_post(url: str, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int | None = None) -> requests.Response | None:
    session = _get_session()
    _rotate_ua(session)
    t = timeout or REQUEST_TIMEOUT
    for attempt in range(3):
        try:
            resp = session.post(url, json=json, headers=headers, timeout=t)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = (attempt + 1) * 2.0 + random.uniform(0, 1)
                _LOGGER.warning("rate limited (%s), retrying in %.1fs", resp.status_code, wait)
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as exc:
            wait = (attempt + 1) * 2.0 + random.uniform(0, 1)
            _LOGGER.warning("request failed (%s), retrying in %.1fs", exc, wait)
            time.sleep(wait)
    return None
