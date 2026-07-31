"""将 scapegoat_data/ 下的早期 HTML 日报提取为扁平键值对，录入 reports.db。

设计：
- 用 stdlib html.parser 提取 h1/h2/h3/h4 作为小节标题，聚合其下正文段落。
- 股票清单类(qualitystock/noonnews)额外提取股票名+标签汇总。
- payload 为扁平 dict，适配前端 flattenPayload(一行一个字段)。
- 幂等：save_report 用 INSERT OR REPLACE(rtype, date)。

不覆盖已有 07-30/07-31 等由定时任务写入的数据（仅补充更早日期）。
"""
import html
import json
import os
import re
import sqlite3
from datetime import date
from html.parser import HTMLParser

from deep_fusion.reports.store import save_report

SRC = "/home/AI/scapegoat_data"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "data", "reports.db")

# rtype 映射：文件夹 -> (rtype, 文件日期正则)
JOBS = [
    ("每日复盘", "dailyreview"),
    ("盘前简报", "premarket"),
    ("优质股推送", "qualitystock"),
    ("午间新闻驱动选股", "noonnews"),
]

# 排除非真实报告
SKIP = {"盘前简报模板.html", "2026-07-19-样例.html"}


class ReportExtractor(HTMLParser):
    """提取标题层级 + 小节正文 + 股票清单。"""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.date_str = ""
        self.sections = []          # [(heading, [text_chunks])]
        self._cur = None            # 当前小节 [heading, [chunks]]
        self._buf = []
        self._tags = []
        self._skip = False
        self._heading_text = ""     # 当前正在解析的标题文本
        self._in_heading = False
        self.stocks = []            # [(name, code, tags)]

    def handle_starttag(self, tag, attrs):
        self._tags.append(tag)
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("h1", "h2", "h3", "h4"):
            # 新标题：先把上一小节的缓冲刷入，再开新标题
            self._flush_buf()
            self._in_heading = True
            self._heading_text = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("h1", "h2", "h3", "h4"):
            self._flush_buf()       # 刷标题文本后关闭
            self._in_heading = False
            self._heading_text = ""
        if self._tags:
            self._tags.pop()

    def handle_data(self, data):
        if self._skip:
            return
        t = data.strip()
        if not t:
            return
        if self._in_heading:
            self._heading_text += t
            return
        # 过滤纯 #标签 噪声（如 #短期 #中期 #长期），不进小节值
        if re.fullmatch(r"#[^#\s]{1,6}", t):
            return
        self._buf.append(t)

    def _flush_buf(self):
        if self._in_heading:
            # 收尾标题：h1 作 title，h2/h3/h4 开新小节
            h = self._heading_text.strip()
            if h:
                if not self.title and len(h) < 40:
                    self.title = h
                else:
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", h)
                    if m and not self.date_str:
                        self.date_str = m.group(1)
                    self._cur = [h, []]
                    self.sections.append(self._cur)
            self._heading_text = ""
            return
        # 普通文本：并入当前小节
        text = " ".join(self._buf).strip()
        self._buf = []
        if not text:
            return
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m and not self.date_str:
            self.date_str = m.group(1)
        if self._cur is not None:
            self._cur[1].append(text)


def _post_process(parser, raw_text):
    """从纯文本中提取股票名+标签，补充到 parser.stocks。"""
    # 找 “名字 + 6位数字代码” 模式
    for m in re.finditer(r"([\u4e00-\u9fa5]{2,6})\s*(\d{6})", raw_text):
        name = m.group(1)
        code = m.group(2)
        # 提取该股票后的标签
        after = raw_text[m.end(): m.end() + 40]
        tags = re.findall(r"#(短期|中期|长期)", after)
        parser.stocks.append((name, code, tags))


def extract(path):
    raw = open(path, encoding="utf-8").read()
    # 去 style/script
    raw = re.sub(r"<style.*?</style>", "", raw, flags=re.S)
    raw = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    p = ReportExtractor()
    p.feed(raw)
    # 纯文本（去所有标签）用于股票提取
    txt = re.sub(r"<[^>]+>", "\n", raw)
    txt = html.unescape(txt)
    txt = "\n".join(l.strip() for l in txt.splitlines() if l.strip())
    _post_process(p, txt)
    return p, txt


def build_payload(rtype, parser, txt):
    payload = {}
    if parser.title:
        payload["报告类型"] = parser.title
    if parser.date_str:
        payload["日期"] = parser.date_str
    # 聚合小节
    for heading, chunks in parser.sections:
        body = " ".join(chunks).strip()
        body = re.sub(r"\s+", " ", body)
        if not body:
            continue
        # 截断过长文本，避免前端一字段占满
        if len(body) > 400:
            body = body[:400] + "…"
        key = heading[:20] or "要点"
        # 同名校验避免覆盖
        if key in payload:
            key = f"{key}({len(payload)})"
        payload[key] = body
    # 股票清单
    if parser.stocks:
        names = []
        seen = set()
        for name, code, tags in parser.stocks:
            if name in seen:
                continue
            seen.add(name)
            tag = "#" + "/".join(tags) if tags else ""
            names.append(f"{name}{tag}" if tag else name)
        if names:
            payload["推送标的"] = "、".join(names[:30])
    # 兜底：若没有任何小节，放摘要
    if len(payload) <= 2:
        summary = re.sub(r"\s+", " ", txt)[:600]
        payload["摘要"] = summary
    return payload


def file_date(fname, folder):
    # 午间文件：午间-2026-07-23.html
    m = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    if m:
        return m.group(1)
    # 盘前简报：2026-07-22.html
    m = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    return m.group(1) if m else None


def main():
    total = 0
    for folder, rtype in JOBS:
        d = os.path.join(SRC, folder)
        if not os.path.isdir(d):
            print(f"[跳过] 目录不存在: {d}")
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".html"):
                continue
            if fname in SKIP:
                print(f"[跳过] {folder}/{fname} (非真实报告)")
                continue
            rdate = file_date(fname, folder)
            if not rdate:
                print(f"[跳过] 无法解析日期: {folder}/{fname}")
                continue
            path = os.path.join(d, fname)
            parser, txt = extract(path)
            payload = build_payload(rtype, parser, txt)
            save_report(rtype, rdate, payload, db_path=DB)
            total += 1
            print(f"[导入] {rtype} {rdate} 字段数={len(payload)} <- {folder}/{fname}")
    print(f"\n完成：共导入 {total} 份报告 -> {DB}")


if __name__ == "__main__":
    main()
