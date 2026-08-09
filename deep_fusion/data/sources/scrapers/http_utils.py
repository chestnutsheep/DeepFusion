#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 工具：requests 封装 + 六级降级链 + 反爬 headers。

来源：cnfinancialscraper skill（全能金融爬虫 v4.7.1）。
依赖：requests、beautifulsoup4（bs4 缺失时自动降级为内置正则解析）。

注意：本项目代理由 clash-verge 全局接管（127.0.0.1:7897），
requests 无需手动设置 HTTPS_PROXY。腾讯源走直连，始终可作兜底。
"""
import re
import time
import random
import urllib.parse
import requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:
    BeautifulSoup = None
    HAS_BS4 = False

DEFAULT_TIMEOUT = 15
DEFAULT_MAX_RETRIES = 3

# 公共反爬 headers 池（避免每个调用方重复定义，且解决重复 key 冲突）
_HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    },
]


def _merge_headers(headers=None):
    """合并默认反爬 headers 与调用方自定义 headers，解决重复 key 冲突。

    调用方传入的 headers 优先级高于默认池。
    """
    base = dict(random.choice(_HEADERS_POOL))
    if headers:
        base.update(headers)
    return base


def http_get(url, headers=None, timeout=DEFAULT_TIMEOUT, max_retries=DEFAULT_MAX_RETRIES,
             return_binary=False, verify=True):
    """六级降级 GET：重试 → 换 UA → 换 Accept → 延长超时 → 关证书校验 → 失败返回 None。

    Args:
        url: 目标 URL
        headers: 调用方自定义 headers（会与默认反爬池合并，调用方优先）
        timeout: 基础超时秒数
        max_retries: 最大重试次数
        return_binary: True 返回 bytes，False 返回 str(utf-8/safe decode)
        verify: TLS 证书校验开关
    Returns:
        str / bytes / None（全部失败）
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            h = _merge_headers(headers)
            # 降级阶梯：第 2 次起关证书校验，第 3 次起延长超时
            cur_verify = verify if attempt < 2 else False
            cur_timeout = timeout if attempt < 2 else timeout * 2
            resp = requests.get(url, headers=h, timeout=cur_timeout, verify=cur_verify)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code == 200:
                return resp.content if return_binary else resp.text
            last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(random.uniform(0.5, 1.5) * (attempt + 1))
    print(f"[http_get] 失败 {url} | {last_err}")
    return None


def http_get_json(url, headers=None, timeout=DEFAULT_TIMEOUT, max_retries=DEFAULT_MAX_RETRIES,
                  verify=True):
    """GET 并解析 JSON。"""
    text = http_get(url, headers=headers, timeout=timeout, max_retries=max_retries, verify=verify)
    if not text:
        return None
    try:
        return __import__("json").loads(text)
    except Exception as e:
        print(f"[http_get_json] JSON 解析失败 {url} | {e}")
        return None


def parse_html(html, parser="html.parser"):
    """优先 bs4，缺失则降级为 None（调用方走正则）。"""
    if HAS_BS4 and html:
        return BeautifulSoup(html, parser)
    return None


# 便捷：从文本中提取所有 http(s) 链接
def extract_links(text):
    if not text:
        return []
    return re.findall(r'href=["\'](https?://[^"\']+)["\']', text)


def safe_decode(content):
    """bytes 安全解码。"""
    if isinstance(content, bytes):
        for enc in ("utf-8", "gb18030", "gbk"):
            try:
                return content.decode(enc)
            except Exception:
                continue
        return content.decode("utf-8", "ignore")
    return content


def urljoin(base, path):
    return urllib.parse.urljoin(base, path)
