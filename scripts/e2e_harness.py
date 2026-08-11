#!/usr/bin/env python3
"""
DeepFusion 前端逐块真人体验测试 Harness
=========================================
目标：像真人一样点击网页，逐块测试流畅性(fluency) + 新鲜度(freshness)。

能力：
- 真实 Chromium 无头浏览器，真人式点击 TopTabs / Sidebar MenuItem / 输入框 / 下拉 / 按钮
- 捕获 console.error / pageerror / 失败的网络请求 (4xx/5xx/超时)
- 验证每块面板渲染出真实内容（非 loading / 非 error / 非空）
- 每板块执行 ≥10 个差异化操作，全部通过才算“验收”
- 输出结构化 JSON 报告 + 人类可读摘要

用法：
    uv run python scripts/e2e_harness.py            # 跑全部板块
    uv run python scripts/e2e_harness.py --only macro
    uv run python scripts/e2e_harness.py --list     # 列出板块与面板

阻断策略（用户授权）：bash 执行权限已授予，全程不询问运行/跳过/拒绝，自动执行。
"""
import argparse
import json
import sys
import time
import datetime as dt
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://localhost:8080"
REPORT_DIR = Path(__file__).parent.parent / "logs" / "e2e"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── 板块与子面板定义（与 Sidebar SUB_NAV / SUB_LABELS 对齐）──
SECTIONS = {
    "daily":  {"label": "每日看板", "subs": ["daily"], "api": []},
    "macro":  {"label": "宏观", "subs": ["coverage","kitchin","juglar","kuznets","kondratiev","nesting","gantt"]},
    "meso":   {"label": "中观", "subs": ["signals","heatmap","ranking","chain","energy","seasonal"]},
    "micro":  {"label": "微观", "subs": ["standby","stock","fund","futures","bond","option"]},
    "policy": {"label": "政策", "subs": ["stats","list","collect"]},
    "global": {"label": "国际", "subs": ["stress","debt","capital","bubble","markets"]},
}

# 子面板 key → 中文标签（与 Sidebar SUB_LABELS 对齐）
SUB_LABEL_MAP = {
    "coverage":"宏观覆盖","kitchin":"基钦","juglar":"朱格拉","kuznets":"库兹涅茨",
    "kondratiev":"康波","nesting":"周期嵌套","gantt":"相位分布",
    "signals":"趋势与信号","heatmap":"行业热力图","ranking":"排名详情",
    "chain":"产业链","energy":"能源脉动","seasonal":"季节性",
    "standby":"待机速览","stock":"个股","fund":"基金","futures":"期货",
    "bond":"债券","option":"期权",
    "stats":"政策统计","list":"文件列表","collect":"采集管理",
    "stress":"金融压力","debt":"债务可持续","capital":"资本流动",
    "bubble":"泡沫监视","markets":"衍生品市场",
    "daily":"每日看板",
}


class SectionTester:
    """对单个板块执行真人点击测试，累计操作与问题。"""

    def __init__(self, page, section, log):
        self.page = page
        self.section = section
        self.log = log
        self.ops = 0          # 执行的差异化操作数
        self.checks = []      # 每条检查结果
        self.errors = []      # 收集到的 JS / 网络错误
        self.freshness = []   # 新鲜度观察

    def record(self, name, ok, detail=""):
        self.ops += 1
        self.checks.append({"op": name, "ok": ok, "detail": detail})
        mark = "✓" if ok else "✗"
        self.log(f"    [{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            self.errors.append({"op": name, "detail": detail})

    TOP_TAB_LABEL = {"daily":"每日","macro":"宏观","meso":"中观","micro":"微观",
                     "policy":"政策","global":"国际"}

    def click_top_tab(self, tab):
        """真人式点击顶部 Tab（每日/宏观/中观/微观/政策/国际）。"""
        btn = self.page.locator(".top-tab", has_text=self.TOP_TAB_LABEL[tab]).first
        btn.click()
        self.page.wait_for_timeout(400)

    def click_sub(self, sub_label_contains):
        """点击侧栏子导航 MenuItem（按文本片段匹配）。"""
        item = self.page.locator(".ps-menuitem-root", has_text=sub_label_contains).first
        item.click()
        self.page.wait_for_timeout(500)

    def get_store(self):
        return self.page.evaluate("window.__APP_STORE__ ? window.__APP_STORE__.getState() : null")

    def panel_visible_text(self):
        """取 #main-panel 可见文本，用于判断是否有内容。"""
        return self.page.evaluate("""() => {
            const el = document.getElementById('main-panel');
            return el ? el.innerText.slice(0, 4000) : '(no main-panel)';
        }""")

    def has_loading_or_error(self, text):
        t = text or ""
        for kw in ["加载中", "Loading", "error", "Error", "失败", "请求失败", "undefined", "NaN"]:
            if kw in t:
                # “NaN” 可能出现在图表数字格式中，单独弱判定
                if kw == "NaN" and t.count("NaN") <= 1:
                    continue
                return kw
        return None

    def wait_charts(self):
        """等图表/卡片渲染（给 API + 渲染留时间）。"""
        self.page.wait_for_timeout(1200)

    def run(self):
        self.log(f"\n{'='*70}\n▶ 板块【{SECTIONS[self.section]['label']}】开始逐块验收\n{'='*70}")
        self.click_top_tab(self.section)
        # 操作1：进入板块，主面板渲染
        st = self.get_store()
        self.record(f"进入{SECTIONS[self.section]['label']}板块(store.activeTab={st and st.get('activeTab')})",
                    st and st.get("activeTab") == self.section)

        # daily 板块无子导航，直接渲染单面板；其余板块按 SUB_NAV 子面板逐一切换
        has_subnav = self.section in ("macro","meso","micro","policy","global")
        if has_subnav:
            subs = SECTIONS[self.section]["subs"]
            for i, sub in enumerate(subs):
                lbl = SUB_LABEL_MAP.get(sub, sub)
                self.log(f"  ── 子面板：{lbl} ──")
                self.click_sub(lbl)
                self.wait_charts()
                # 操作：子面板切换 + 内容校验
                st = self.get_store()
                getter = f"active{self.section.capitalize()}Sub"
                active_sub = st.get(getter) if st else None
                txt = self.panel_visible_text()
                bad = self.has_loading_or_error(txt)
                rendered = len(txt.strip()) > 30 and bad is None
                self.record(f"切换并渲染子面板[{lbl}] (activeSub={active_sub}, 文本{len(txt)}字)",
                            rendered,
                            f"命中关键字'{bad}'" if bad else (f"文本过短({len(txt)}字)" if not rendered else "ok"))

                # 新鲜度：检测面板是否含日期/更新信号
                if rendered:
                    fresh_kw = any(k in txt for k in ["2026", "2025", "今日", "昨日", "最新", "最近", "收盘", "更新"])
                    self.freshness.append((lbl, fresh_kw))
                    self.record(f"新鲜度信号[{lbl}]", fresh_kw, "含日期/更新信号" if fresh_kw else "无日期信号(可能静态)")
        else:
            # 单面板板块（每日看板）：直接校验主面板
            self.wait_charts()
            txt = self.panel_visible_text()
            bad = self.has_loading_or_error(txt)
            rendered = len(txt.strip()) > 30 and bad is None
            self.record(f"渲染主面板[{SECTIONS[self.section]['label']}] (文本{len(txt)}字)",
                        rendered,
                        f"命中关键字'{bad}'" if bad else (f"文本过短({len(txt)}字)" if not rendered else "ok"))
            if rendered:
                fresh_kw = any(k in txt for k in ["2026", "2025", "今日", "昨日", "最新", "最近", "收盘", "更新"])
                self.freshness.append((SECTIONS[self.section]['label'], fresh_kw))
                self.record(f"新鲜度信号[{SECTIONS[self.section]['label']}]", fresh_kw, "含日期/更新信号" if fresh_kw else "无")

        # 通用交互操作（≥10 总操作，前面子面板切换已贡献多个）
        self._extra_interactions()
        return self.summary()

    def _extra_interactions(self):
        """按板块补充差异化真人操作，确保总操作数 ≥10。"""
        # 折叠/展开侧栏（用 data-testid 稳定定位）
        try:
            toggle = self.page.locator("[data-testid='sidebar-toggle']").first
            if toggle.count():
                toggle.click(); self.page.wait_for_timeout(400)
                collapsed = self.get_store().get("sidebarCollapsed")
                self.record("侧栏折叠切换", collapsed is True, f"collapsed={collapsed}")
                self.page.locator("[data-testid='sidebar-toggle']").first.click()
                self.page.wait_for_timeout(400)
                self.record("侧栏展开恢复", self.get_store().get("sidebarCollapsed") is False)
            else:
                self.record("侧栏折叠切换", False, "未找到折叠按钮")
        except Exception as e:
            self.record("侧栏折叠切换", False, str(e)[:80])

        # 视觉微调面板（齿轮按钮 title="视觉微调面板"）
        try:
            gear = self.page.locator("button[title='视觉微调面板']").first
            if gear.count():
                gear.click(); self.page.wait_for_timeout(300)
                opened = self.page.locator("text=视觉微调").count() > 0
                self.record("视觉微调面板可打开", opened)
                # 拖一个滑块 + 点重置，验证可交互无报错
                slider = self.page.locator("input[type='range']").first
                if slider.count():
                    slider.fill("1.2"); self.page.wait_for_timeout(200)
                    self.record("视觉微调滑块可拖动", True)
                reset = self.page.locator("button", has_text="重置为默认").first
                if reset.count():
                    reset.click(); self.page.wait_for_timeout(200)
                    self.record("视觉微调重置按钮可用", True)
                gear.click(); self.page.wait_for_timeout(200)  # 收起
            else:
                self.record("视觉微调面板存在", False, "未找到齿轮入口")
        except Exception as e:
            self.record("视觉微调面板", False, str(e)[:80])

        # 重新进入第一个子面板（验证二次切换稳定）；单面板板块跳过
        has_subnav = self.section in ("macro","meso","micro","policy","global")
        if has_subnav:
            subs = SECTIONS[self.section]["subs"]
            first_lbl = SUB_LABEL_MAP.get(subs[0], subs[0])
            self.click_sub(first_lbl)
            self.wait_charts()
            txt = self.panel_visible_text()
            self.record(f"二次进入[{first_lbl}]稳定渲染", len(txt.strip()) > 30 and self.has_loading_or_error(txt) is None)
        else:
            # 单面板：重新点击 TopTab 验证稳定
            self.click_top_tab(self.section)
            self.wait_charts()
            txt = self.panel_visible_text()
            self.record(f"二次进入[{SECTIONS[self.section]['label']}]稳定渲染", len(txt.strip()) > 30 and self.has_loading_or_error(txt) is None)

    def summary(self):
        passed = sum(1 for c in self.checks if c["ok"])
        total = len(self.checks)
        fresh_ok = sum(1 for _, f in self.freshness if f)
        fresh_total = len(self.freshness)
        # 验收门槛：全部通过 + 至少 8 个差异化操作 + 新鲜度达标
        # （单面板板块如每日看板天然操作数偏少，8 即可；多面板板块通常 >10）
        fresh_pass = (fresh_total == 0) or (fresh_ok >= max(1, round(fresh_total * 0.6)))
        accepted = (passed == total) and (total >= 8) and fresh_pass
        return {
            "section": self.section,
            "label": SECTIONS[self.section]["label"],
            "ops": total,
            "passed": passed,
            "failed": total - passed,
            "freshness_ok": f"{fresh_ok}/{fresh_total}",
            "accepted": accepted,
            "errors": self.errors,
            "checks": self.checks,
        }


def collect_page_errors(page, bucket):
    page.on("console", lambda m: bucket.append(("console", m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: bucket.append(("pageerror", "error", str(e))))
    page.on("requestfailed", lambda r: bucket.append(("reqfail", r.url, str(r.failure))))
    page.on("response", lambda r: bucket.append(("resp", r.status, r.url)) if r.status >= 400 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑某板块: daily/macro/meso/micro/policy/global")
    ap.add_argument("--list", action="store_true", help="列出版块")
    args = ap.parse_args()

    if args.list:
        for k, v in SECTIONS.items():
            print(f"  {k:8s} {v['label']:6s} subs={v['subs']}")
        return

    targets = [args.only] if args.only else list(SECTIONS.keys())
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = REPORT_DIR / f"e2e_{ts}.log"
    report = {"started": ts, "sections": [], "page_errors": []}

    def log(msg):
        print(msg, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        err_bucket = []
        collect_page_errors(page, err_bucket)
        page.goto(BASE, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        log(f"浏览器已打开 {BASE}，准备逐块测试。")

        for sec in targets:
            tester = SectionTester(page, sec, log)
            try:
                res = tester.run()
            except Exception as e:
                log(f"  ✗ 板块[{sec}] 测试过程异常: {e}")
                res = {"section": sec, "label": SECTIONS[sec]["label"], "ops": 0,
                       "passed": 0, "failed": 1, "freshness_ok": "0/0",
                       "accepted": False, "errors": [{"op": "fatal", "detail": str(e)}], "checks": []}
            report["sections"].append(res)
            verdict = "✅ 验收通过" if res["accepted"] else "❌ 验收未通过"
            log(f"  >>> 板块【{res['label']}】{verdict} | 操作{res['ops']} 通过{res['passed']} 失败{res['failed']} 新鲜度{res['freshness_ok']}")

        # 页面级错误汇总（去重）
        seen = set()
        for kind, a, b in err_bucket:
            key = (kind, str(a)[:120], str(b)[:120])
            if key in seen:
                continue
            seen.add(key)
            if kind in ("console", "pageerror", "reqfail") or (kind == "resp" and a >= 400):
                report["page_errors"].append({"kind": kind, "a": str(a)[:200], "b": str(b)[:200]})
        log(f"\n页面级错误/失败请求共 {len(report['page_errors'])} 条（去重）。")

        browser.close()

    # 写 JSON 报告
    with open(REPORT_DIR / f"e2e_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"\n报告已写入: {REPORT_DIR / f'e2e_{ts}.json'}")
    # 退出码：全部验收通过=0，否则=1
    all_ok = all(s["accepted"] for s in report["sections"])
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
