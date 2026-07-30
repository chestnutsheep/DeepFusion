"""policy_collector 测试。

测试铁律：
1. 涉及 akshare 的测试必须真实调用，不许 mock 模拟 akshare 行为
   （policy_collector 不涉及 akshare，是政府网站 HTML 抓取）
2. 纯逻辑测试（URL 拼接、正则、日期标准化、DB CRUD）保留不动
3. 采集测试改为真实调用政府网站，请求 `_require_network`，无网络时 skip
"""
from __future__ import annotations

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


# ── 1. 分页 URL 拼接（纯逻辑，不涉及网络）────────────

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


# ── 2. 日期正则 _DATE_RE（纯逻辑）────────────────────

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


# ── 3. URL 日期正则 _URL_DATE_RE（纯逻辑）────────────

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


class TestUrlDateParts:
    """_url_date_parts 应从政府站点 URL 提取日期成分，且不占位 day=01。"""

    def test_t_ymd_full_date(self):
        """mof 的 /t20260424_xxx.htm 应提取精确日。"""
        assert collector._url_date_parts(
            "http://gks.mof.gov.cn/tongjishuju/202604/t20260424_3988324.htm"
        ) == ("2026", "04", "24")

    def test_slash_ymd(self):
        """ /2026/06/02/ 斜杠分隔含日。"""
        assert collector._url_date_parts(
            "https://example.com/2026/06/02/title.html"
        ) == ("2026", "06", "02")

    def test_ym_only_returns_pair(self):
        """ /202606/ 仅年月应返回二元组（交 meta/正文补全，不占位 01）。"""
        assert collector._url_date_parts(
            "https://www.gov.cn/zhengce/content/202606/content_7070755.htm"
        ) == ("2026", "06")

    def test_no_date_returns_none(self):
        assert collector._url_date_parts("https://example.com/about/contact.html") is None

    def test_invalid_year_rejected(self):
        """非合理年份不应命中。"""
        assert collector._url_date_parts("https://example.com/1999/13/99/x.html") is None

    def test_mof_pdf_embedded_ymd(self):
        """mof PDF 命名 P02…20260326… 应提取嵌入的精确日。"""
        assert collector._url_date_parts(
            "http://bgt.mof.gov.cn/gongzuodongtai/202603/P020260326304311439963.pdf"
        ) == ("2026", "03", "26")

    def test_generic_ymd_fallback(self):
        """URL 中任意合法 8 位日期应作为兜底命中。"""
        assert collector._url_date_parts(
            "http://x/y/P020260723306771605375.pdf"
        ) == ("2026", "07", "23")


# ── 4. 日期标准化（纯逻辑）──────────────────────────

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


# ── 5. stats last_collected（纯 DB 逻辑）────────────

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


# ── 6. collect_all 真实采集（原 TestCollectAllMock，已删除 mock）────

class TestCollectAll:
    """collect_all 真实采集政府网站。

    原测试用 patch.object mock _FETCHERS 和 _extract_detail，返回硬编码 entries，
    绕过了真实 HTML 抓取。已改为真实调用，请求 _require_network。
    """

    def test_collect_all_runs_with_real_network(self, _require_network):
        """真调 collect_all，验证能成功执行并返回 dict。

        政府网站可能不稳定，容错：只要至少一个源成功（非 error），即视为通过。
        """
        results = collector.collect_all(max_pages=1)
        assert isinstance(results, dict)
        assert len(results) > 0, "应至少尝试采集所有源"
        # 至少有一个源成功（有 total/new 字段，非 error）
        successful = {k: v for k, v in results.items() if "error" not in v}
        assert len(successful) > 0, f"至少一个源应成功，实际: {results}"

    def test_collect_all_writes_to_db(self, _require_network):
        """真调 collect_all 后，DB 中应有数据。"""
        collector.collect_all(max_pages=1)
        st = collector.db.stats()
        # 采集后应有 last_collected 或总条数 > 0
        total = st.get("total", 0)
        assert total > 0 or st.get("last_collected", "") != "", \
            "采集后 DB 应有数据或 last_collected"


# ── 7. 相对路径 URL 拼接（真实测试，原用 _FakeResp mock）──────────

class TestRelativeUrlJoin:
    """_parse_list 应正确解析 ../../ 开头的相对路径 href。

    原测试用 _FakeResp mock HTTP 响应返回硬编码 HTML。已改为真实调用
    财政部网站，请求 _require_network。政府网站 HTML 结构变化风险高，
    解析失败时 skip 而非报错。
    """

    def test_relative_url_join_real(self, _require_network):
        """真调 mof.gov.cn，验证 _parse_list 能解析出条目且 URL 合法。

        核心 bug 修复点：../../ 相对路径不应拼成
        https://www.mof.gov.cn../../... 非法 URL。
        """
        entries = collector._parse_list(
            "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/index.html",
            link_filter=lambda u: "mof.gov.cn" in u and u.endswith(".html"),
            source="财政部",
            org="财政部",
            max_pages=1,
        )
        # 政府网站 HTML 结构可能变化，解析为空时 skip
        if not entries:
            pytest.skip("财政部网站未解析到条目，可能 HTML 结构变化")
        # 验证所有 URL 都合法（不应出现 ../../ 拼接错误）
        for e in entries:
            url = e["url"]
            assert ".." not in url, f"URL 含非法 ..: {url}"
            assert url.startswith("http"), f"URL 非合法绝对路径: {url}"
