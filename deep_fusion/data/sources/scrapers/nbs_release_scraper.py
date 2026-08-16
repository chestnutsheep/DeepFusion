#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国家统计局新闻稿爬虫 — 补齐朱格拉周期失效指标。

朱格拉周期 4 指标中，NBS 官方 data API（data.stats.gov.cn）对以下指标
**根本不存在全国月度汇总序列**（仅分行业/年度），故接口返回空：
  - 设备工器具购置投资 (equip_yoy)        —— 核心权重 0.4
  - 制造业固定资产投资   (manufacturing_yoy) —— 权重 0.25
  - 工业产能利用率       (capacity_util)   —— 权重 0.2

这三个指标国家统计局**仅在官网新闻稿中发布**（月度/季度）。
本模块用 **playwright 渲染** 绕过 NBS 的 JS 反爬挑战，爬取新闻稿 HTML 提取数值：
  - 固定资产投资稿（含设备工器具、制造业）：https://www.stats.gov.cn/sj/zxfb/index_N.html
  - 产能利用率稿：https://www.stats.gov.cn/sj/zxfbhjd/index_N.html

数据口径与朱格拉原有定义完全一致（累计同比增长 / 季度当季值），
**不触及任何周期计算/相位逻辑（红线）**。

注：playwright 首次使用需 `playwright install chromium`。若不可用则降级为
http_utils（可能被反爬拦截，best-effort）。
"""
import re
import logging

logger = logging.getLogger(__name__)

_NBS_ZXFB = "https://www.stats.gov.cn/sj/zxfb/"
_NBS_ZXBHJD = "https://www.stats.gov.cn/sj/zxfbhjd/"
_MAX_PAGES = 24  # 翻页上限：足够覆盖 ~2 年月度 / ~6 年季度历史


def _get_browser():
    """懒加载 playwright 浏览器（避免无头环境误报导入错误）。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    return pw, browser


# ───────────────────────── 解析函数 ─────────────────────────

def _parse_equip(text: str) -> float | None:
    """设备工器具购置累计同比。新闻稿表格结构，标签与数值分行。"""
    m = re.search(r"设备工器具购置[\s\S]{0,40}?(-?[\d.]+)", text)
    return float(m.group(1)) if m else None


def _parse_mfg(text: str) -> float | None:
    """制造业投资累计同比：『制造业投资增长6.2%』或『制造业投资下降0.4%』。"""
    m = re.search(r"制造业投资(增长|下降)\s*(-?[\d.]+)\s*%", text)
    if m:
        sign = 1.0 if m.group(1) == "增长" else -1.0
        return sign * float(m.group(2))
    m2 = re.search(r"制造业投资[^\d\-]{0,8}?(-?[\d.]+)\s*%", text)
    return float(m2.group(1)) if m2 else None


def _parse_capacity(text: str) -> float | None:
    """『全国规模以上工业产能利用率为73.6%』或『产能利用率为73.6%』。"""
    m = re.search(r"产能利用率为\s*([\d.]+)\s*%", text)
    if m:
        return float(m.group(1))
    m2 = re.search(r"工业产能利用率为\s*([\d.]+)\s*%", text)
    return float(m2.group(1)) if m2 else None


def _period_from_fix_title(title: str) -> str | None:
    """『2026年1—6月份全国固定资产投资基本情况』→ '202606'（截止月份）。"""
    m = re.search(r"(\d{4})年(\d{1,2})[—-](\d{1,2})月份", title)
    if m:
        return f"{m.group(1)}{int(m.group(3)):02d}"
    return None


def _period_from_cap_title(title: str) -> str | None:
    """『2026年二季度全国规模以上工业产能利用率为73.0%』→ '2026Q2'。"""
    m = re.search(r"(\d{4})年(一|二|三|四)季度", title)
    if not m:
        return None
    y = m.group(1)
    q = {"一": 1, "二": 2, "三": 3, "四": 4}[m.group(2)]
    return f"{y}Q{q}"


# ───────────────────────── 爬取主函数（playwright） ─────────────────────────

def _iter_list_pages(browser, base_url: str):
    """用 playwright 翻页遍历列表，yield (title_text, abs_href)。"""
    page = browser.new_page()
    empty_streak = 0
    try:
        for pnum in range(2, _MAX_PAGES + 1):
            url = f"{base_url}index_{pnum}.html"
            try:
                page.goto(url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2500)  # 等列表 JS 渲染
            except Exception as e:
                logger.warning(f"列表页加载失败 {url}: {e}")
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            try:
                links = page.eval_on_selector_all(
                    "a[href]", "els=>els.map(e=>({t:(e.textContent||'').trim(),h:e.href}))"
                )
            except Exception as e:
                logger.warning(f"列表页解析失败 {url}: {e}")
                links = []
            if not links:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            empty_streak = 0
            for l in links:
                href = l.get("h", "")
                if href and href.startswith("/"):
                    href = "https://www.stats.gov.cn" + href
                yield l.get("t", ""), href
    finally:
        try:
            page.close()
        except Exception:
            pass


def collect_equip_mfg_history() -> tuple[list[str], list[float], list[float]]:
    """爬全部历史固定资产投资稿，返回 (periods, equip_yoy, manufacturing_yoy)。

    月度累计同比序列，period 为 'YYYYMM'（数据截止月）。
    """
    try:
        pw, browser = _get_browser()
    except Exception as e:
        logger.warning(f"playwright 不可用，降级 requests: {e}")
        return _collect_equip_mfg_requests()
    periods, equips, mfgs = [], [], []
    seen: set[str] = set()
    try:
        for title, href in _iter_list_pages(browser, _NBS_ZXFB):
            if "固定资产投资" not in title or "产能" in title:
                continue
            period = _period_from_fix_title(title)
            if not period or period in seen:
                continue
            try:
                detail = browser.new_page()
                detail.goto(href, timeout=30000, wait_until="domcontentloaded")
                detail.wait_for_selector("body", timeout=15000)
                text = detail.inner_text("body")
                detail.close()
            except Exception as e:
                logger.warning(f"详情页失败 {href}: {e}")
                continue
            eq = _parse_equip(text)
            mf = _parse_mfg(text)
            if eq is None and mf is None:
                continue
            seen.add(period)
            periods.append(period)
            equips.append(eq if eq is not None else float("nan"))
            mfgs.append(mf if mf is not None else float("nan"))
    finally:
        try:
            browser.close(); pw.stop()
        except Exception:
            pass
    order = sorted(range(len(periods)), key=lambda i: periods[i])
    return ([periods[i] for i in order], [equips[i] for i in order], [mfgs[i] for i in order])


def collect_capacity_util_history() -> tuple[list[str], list[float]]:
    """爬全部历史产能利用率稿，返回 (periods, values)，period='YYYYQQ'。"""
    try:
        pw, browser = _get_browser()
    except Exception as e:
        logger.warning(f"playwright 不可用，降级 requests: {e}")
        return _collect_capacity_requests()
    periods, values = [], []
    seen: set[str] = set()
    try:
        for title, href in _iter_list_pages(browser, _NBS_ZXBHJD):
            if "规模以上工业产能利用率" not in title:
                continue
            period = _period_from_cap_title(title)
            if not period or period in seen:
                continue
            try:
                detail = browser.new_page()
                detail.goto(href, timeout=30000, wait_until="domcontentloaded")
                detail.wait_for_selector("body", timeout=15000)
                text = detail.inner_text("body")
                detail.close()
            except Exception as e:
                logger.warning(f"详情页失败 {href}: {e}")
                continue
            val = _parse_capacity(text)
            if val is None:
                continue
            seen.add(period)
            periods.append(period)
            values.append(val)
    finally:
        try:
            browser.close(); pw.stop()
        except Exception:
            pass
    order = sorted(range(len(periods)), key=lambda i: periods[i])
    return ([periods[i] for i in order], [values[i] for i in order])


# ───────────────────────── requests 降级（可能被反爬拦截） ─────────────────────────

def _collect_equip_mfg_requests():
    from .http_utils import http_get, parse_html
    periods, equips, mfgs = [], [], []
    seen: set[str] = set()
    for pnum in range(1, _MAX_PAGES + 1):
        url = _NBS_ZXFB if pnum == 1 else f"{_NBS_ZXFB}index_{pnum}.html"
        html = http_get(url)
        if not html:
            continue
        soup = parse_html(html)
        if not soup:
            continue
        found = False
        for a in soup.find_all("a", href=True):
            t = a.get_text(strip=True)
            if "固定资产投资" not in t or "产能" in t:
                continue
            period = _period_from_fix_title(t)
            if not period or period in seen:
                continue
            href = a["href"]
            abs_url = href if href.startswith("http") else (_NBS_ZXFB + href.lstrip("./"))
            art = http_get(abs_url)
            if not art:
                continue
            s2 = parse_html(art)
            text = s2.get_text() if s2 else art
            eq, mf = _parse_equip(text), _parse_mfg(text)
            if eq is None and mf is None:
                continue
            seen.add(period)
            periods.append(period)
            equips.append(eq if eq is not None else float("nan"))
            mfgs.append(mf if mf is not None else float("nan"))
            found = True
        if not found and pnum > 3:
            break
    order = sorted(range(len(periods)), key=lambda i: periods[i])
    return ([periods[i] for i in order], [equips[i] for i in order], [mfgs[i] for i in order])


def _collect_capacity_requests():
    from .http_utils import http_get, parse_html
    periods, values = [], []
    seen: set[str] = set()
    for pnum in range(1, _MAX_PAGES + 1):
        url = _NBS_ZXBHJD if pnum == 1 else f"{_NBS_ZXBHJD}index_{pnum}.html"
        html = http_get(url)
        if not html:
            continue
        soup = parse_html(html)
        if not soup:
            continue
        found = False
        for a in soup.find_all("a", href=True):
            t = a.get_text(strip=True)
            if "规模以上工业产能利用率" not in t:
                continue
            period = _period_from_cap_title(t)
            if not period or period in seen:
                continue
            href = a["href"]
            abs_url = href if href.startswith("http") else (_NBS_ZXBHJD + href.lstrip("./"))
            art = http_get(abs_url)
            if not art:
                continue
            s2 = parse_html(art)
            text = s2.get_text() if s2 else art
            val = _parse_capacity(text)
            if val is None:
                continue
            seen.add(period)
            periods.append(period)
            values.append(val)
            found = True
        if not found and pnum > 3:
            break
    order = sorted(range(len(periods)), key=lambda i: periods[i])
    return ([periods[i] for i in order], [values[i] for i in order])


if __name__ == "__main__":
    p, e, m = collect_equip_mfg_history()
    print(f"EQUIP/MFG history: {len(p)} pts, last={p[-1] if p else None}")
    print("  last equip=", e[-1] if e else None, "mfg=", m[-1] if m else None)
    cp, cv = collect_capacity_util_history()
    print(f"CAPACITY history: {len(cp)} pts, last={cp[-1] if cp else None} val={cv[-1] if cv else None}")
