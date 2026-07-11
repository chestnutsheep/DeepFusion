"""policy_collector 采集 + DB 日期标准化测试 (TDD)。

7 组测试：分页URL / 日期正则 / URL日期正则 / 日期标准化 /
stats last_collected / collect_all mock / normalize 调用验证。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from deep_fusion.shared import policy_db as pdb_mod
from deep_fusion.shared.policy_db import PolicyDB
from deep_fusion.data.sources import policy as collector


# ── fixture: 临时内存数据库 ──────────────────────────

@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """将 policy_db 的 DB_PATH 重定向到临时文件，避免污染生产库。"""
    tmp_db = tmp_path / "test_policy.db"
    monkeypatch.setattr(pdb_mod, "DB_PATH", tmp_db)
    # 重置模块级 db 实例的连接，使其指向新路径
    collector.db._conn = None
    yield tmp_db
    if collector.db._conn:
        collector.db._conn.close()
        collector.db._conn = None


# ── 1. 分页 URL 拼接 ─────────────────────────────────

class TestBuildPageUrl:
    """_build_page_url 应正确处理已含 index.html 的 URL。"""

    def test_plain_dir_page1(self):
        assert collector._build_page_url("https://www.gov.cn/zhengce/", 1) == \
            "https://www.gov.cn/zhengce/index.htm"

    def test_plain_dir_page2(self):
        assert collector._build_page_url("https://www.gov.cn/zhengce/", 2) == \
            "https://www.gov.cn/zhengce/index_2.htm"

    def test_with_index_html_page1(self):
        """URL 已含 index.html 时不能拼成 index.htmlindex.htm。"""
        assert collector._build_page_url("https://www.safe.gov.cn/safe/whhl/index.html", 1) == \
            "https://www.safe.gov.cn/safe/whhl/index.htm"

    def test_with_index_html_page2(self):
        assert collector._build_page_url("https://www.safe.gov.cn/safe/whhl/index.html", 2) == \
            "https://www.safe.gov.cn/safe/whhl/index_2.htm"

    def test_with_index_htm_page3(self):
        assert collector._build_page_url("https://www.safe.gov.cn/safe/whhl/index.htm", 3) == \
            "https://www.safe.gov.cn/safe/whhl/index_3.htm"


# ── 2. 日期正则 _DATE_RE ────────────────────────────

class TestDateRegex:
    """_DATE_RE 不应误匹配日期范围如"2025年1-7月"。"""

    def test_does_not_match_range_1_7(self):
        """"2025年1-7月" 不应被匹配为 2025年1月7日。"""
        assert collector._DATE_RE.search("2025年1-7月经济数据") is None

    def test_matches_chinese_date_with_day(self):
        m = collector._DATE_RE.search("发布于2026年6月2日")
        assert m is not None
        assert "2026" in m.group(1)

    def test_matches_iso_date(self):
        m = collector._DATE_RE.search("日期：2026-06-02")
        assert m is not None
        assert m.group(1) == "2026-06-02"

    def test_matches_slash_date(self):
        m = collector._DATE_RE.search("2026/06/02")
        assert m is not None


# ── 3. URL 日期正则 _URL_DATE_RE ────────────────────

class TestUrlDateRegex:
    """_URL_DATE_RE 应从政府站点 URL 路径提取日期。"""

    def test_matches_compact_ymd(self):
        """ /20260602/ 紧凑格式。"""
        m = collector._URL_DATE_RE.search("https://example.com/news/20260602/t123.html")
        assert m is not None
        assert m.group(1) == "2026"

    def test_matches_slash_separated(self):
        """ /2026/06/02/ 斜杠分隔格式。"""
        m = collector._URL_DATE_RE.search("https://example.com/2026/06/02/title.html")
        assert m is not None
        assert m.group(1) == "2026"

    def test_matches_ym_only(self):
        """ /202606/ 仅年月格式。"""
        m = collector._URL_DATE_RE.search("https://stats.gov.cn/sj/zxfb/202606/t20260602.html")
        assert m is not None

    def test_no_match_for_non_date(self):
        """无日期路径不应匹配。"""
        assert collector._URL_DATE_RE.search("https://example.com/about/contact.html") is None


# ── 4. 日期标准化 ───────────────────────────────────

class TestNormalizeDate:
    """_normalize_date 应将各种格式标准化为 ISO。"""

    def test_chinese(self):
        assert pdb_mod._normalize_date("2026年6月2日") == "2026-06-02"

    def test_iso(self):
        assert pdb_mod._normalize_date("2026-06-02") == "2026-06-02"

    def test_slash(self):
        assert pdb_mod._normalize_date("2026/06/02") == "2026-06-02"

    def test_dot(self):
        assert pdb_mod._normalize_date("2026.06.02") == "2026-06-02"

    def test_empty(self):
        assert pdb_mod._normalize_date("") == ""

    def test_unparseable(self):
        assert pdb_mod._normalize_date("近日") == "近日"


# ── 5. stats last_collected ─────────────────────────

class TestStatsLastCollected:
    """db.stats() 应返回 last_collected（最近采集时间）。"""

    def test_returns_last_collected(self):
        collector.db.save({"url": "http://example.com/p1", "title": "测试", "found_at": "2026-07-11T10:00:00"})
        st = collector.db.stats()
        assert "last_collected" in st
        assert st["last_collected"] == "2026-07-11T10:00:00"

    def test_returns_latest_when_multiple(self):
        collector.db.save({"url": "http://example.com/a", "title": "A", "found_at": "2026-07-10T08:00:00"})
        collector.db.save({"url": "http://example.com/b", "title": "B", "found_at": "2026-07-11T12:00:00"})
        collector.db.save({"url": "http://example.com/c", "title": "C", "found_at": "2026-07-09T06:00:00"})
        st = collector.db.stats()
        assert st["last_collected"] == "2026-07-11T12:00:00"

    def test_returns_empty_when_no_data(self):
        st = collector.db.stats()
        assert st.get("last_collected", "") == ""


# ── 6. collect_all mock ─────────────────────────────

class TestCollectAllMock:
    """collect_all 应聚合各 fetcher 的结果并写入 DB。"""

    def test_aggregates_results(self):
        fake_entries = [
            {"title": "政策A", "url": "http://a.com/1", "source": "国务院", "organization": "国务院",
             "publish_date": "", "found_at": "2026-07-11T00:00:00", "body": "", "keywords": ""},
        ]
        with patch.object(collector, "_FETCHERS", [("测试站", lambda max_pages=2: fake_entries)]), \
             patch.object(collector, "_extract_detail", side_effect=lambda e: e):
            results = collector.collect_all(max_pages=1)
        assert "测试站" in results
        assert results["测试站"]["total"] == 1
        assert results["测试站"]["new"] == 1

    def test_skips_existing(self):
        """已存在的 URL 不重复入库。"""
        collector.db.save({"url": "http://a.com/1", "title": "已有", "found_at": "2026-01-01T00:00:00"})
        fake_entries = [
            {"title": "政策A", "url": "http://a.com/1", "source": "国务院", "organization": "国务院",
             "publish_date": "", "found_at": "2026-07-11T00:00:00", "body": "", "keywords": ""},
        ]
        with patch.object(collector, "_FETCHERS", [("测试站", lambda max_pages=2: fake_entries)]), \
             patch.object(collector, "_extract_detail", side_effect=lambda e: e):
            results = collector.collect_all(max_pages=1)
        assert results["测试站"]["new"] == 0


# ── 7. normalize 调用验证 ───────────────────────────

class TestNormalizeCalled:
    """collect_all 应在采集后调用 normalize_all_dates。"""

    def test_calls_normalize(self):
        fake_entries = [
            {"title": "政策A", "url": "http://a.com/1", "source": "国务院", "organization": "国务院",
             "publish_date": "", "found_at": "2026-07-11T00:00:00", "body": "", "keywords": ""},
        ]
        with patch.object(collector, "_FETCHERS", [("测试站", lambda max_pages=2: fake_entries)]), \
             patch.object(collector, "_extract_detail", side_effect=lambda e: e), \
             patch.object(collector.db, "normalize_all_dates", return_value=0) as mock_norm:
            collector.collect_all(max_pages=1)
        mock_norm.assert_called_once()


# ── 8. 相对路径 URL 拼接 ─────────────────────────────

class TestRelativeUrlJoin:
    """_parse_list 应正确解析 ../../ 开头的相对路径 href。"""

    def test_relative_url_join(self):
        """../../ 相对路径不应拼成 https://www.mof.gov.cn../../... 非法 URL。"""
        html = (
            '<html><body>'
            '<a href="../../zhengwuxinxi/caizhengxinwen/202606/t20260629.html">'
            '财政部关于2026年政策通知标题足够长'
            '</a>'
            '</body></html>'
        )

        class _FakeResp:
            status_code = 200
            encoding = "utf-8"
            apparent_encoding = "utf-8"
            text = html

        with patch.object(collector._SESSION, "get", return_value=_FakeResp()):
            entries = collector._parse_list(
                "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/index.html",
                link_filter=lambda u: True,
                source="财政部",
                org="财政部",
                max_pages=1,
            )

        assert len(entries) == 1
        assert entries[0]["url"] == \
            "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/202606/t20260629.html"
        # 关键：不能出现非法的域名后直接跟 ../
        assert "../" not in entries[0]["url"]

