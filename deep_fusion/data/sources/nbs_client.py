"""NBS data source adapter - standalone client for data.stats.gov.cn"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_NBS_BASE_URL = "https://data.stats.gov.cn/dg/website/publicrelease/web/external"
_NBS_ROOT_IDS = {
    1: "fc982599aa684be7969d7b90b1bd0e84",
    2: "a94b8b7365a94874968cabbe392cf679",
    3: "1dcdcab5f2c6476aa8cd5e5dca351159",
}
_NBS_CACHE_DIR = Path.home() / ".cache" / "deep_fusion" / "nbs"
_NBS_REQUEST_INTERVAL = 0.6
_NBS_CACHE_DIR = Path.home() / ".cache" / "deep_fusion" / "nbs"
_NBS_REQUEST_INTERVAL = 0.6


class _NbsClient:
    __shared: "_NbsClient | None" = None

    def __new__(cls, *args, **kwargs):
        if cls.__shared is None:
            cls.__shared = super().__new__(cls)
        return cls.__shared

    def __init__(self, cid_dir: str | Path | None = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.cache_dir = _NBS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self._session.trust_env = False
        # 清除可能从环境继承的代理配置，NBS 网站不支持代理访问
        self._session.proxies = {"http": None, "https": None}
        self._last_request = 0.0
        self._cid_index: list[dict] | None = None
        self._cid_dir = Path(cid_dir) if cid_dir else (
                    Path(__file__).resolve().parent.parent.parent / "shared" / "data")

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < _NBS_REQUEST_INTERVAL:
            time.sleep(_NBS_REQUEST_INTERVAL - elapsed)
        self._last_request = time.time()

    def _cache_get(self, key: str, ttl: int) -> dict | None:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            age = time.time() - path.stat().st_mtime
            if age < ttl:
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    # 缓存文件损坏（半截写/并发写/被kill）时忽略，回退到重新拉取
                    logger.warning("nbs_cache_corrupt", key=key, path=str(path))
                    return None
        return None

    def _cache_set(self, key: str, data):
        import os
        import tempfile
        path = self.cache_dir / f"{key}.json"
        # 原子写：先写临时文件再 replace，避免进程中断留下半截 JSON 导致下次读取崩溃
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp, path)

    def _load_cid_index(self):
        if self._cid_index is not None:
            return
        self._cid_index = []
        for fname in ["nbs_cids_monthly.json", "nbs_cids_quarterly.json", "nbs_cids_annual.json"]:
            path = self._cid_dir / fname
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    logger.warning("nbs_index_corrupt", fname=fname, path=str(path))
                    continue
                freq = "月度" if "monthly" in fname else ("季度" if "quarterly" in fname else "年度")
                for item in data:
                    self._cid_index.append({
                        "cid": item.get("id", ""),
                        "name": item.get("name", ""),
                        "freq": freq,
                        "sdate": item.get("sdate"),
                        "edate": item.get("edate"),
                        "treeinfo_globalid": item.get("treeinfo_globalid", ""),
                    })

    def search(self, keyword: str, freq: str = "") -> list[dict]:
        self._load_cid_index()
        if self._cid_index is None:
            return []
        results = []
        for item in self._cid_index:
            name = item.get("name", "")
            if keyword in name:
                if freq and item.get("freq") != freq:
                    continue
                results.append(dict(item))
        return results

    def get_tree_children(self, pid: str = "", code: str = "1") -> list[dict]:
        self._rate_limit()
        resp = self._session.get(
            f"{_NBS_BASE_URL}/new/queryIndexTreeAsync",
            params={"pid": pid, "code": code},
            timeout=15,
        )
        nodes = resp.json().get("data", [])
        results = []
        for node in nodes:
            results.append({
                "cid": node.get("_id", ""),
                "name": node.get("name", ""),
                "isLeaf": node.get("isLeaf", False),
                "sdate": node.get("sdate"),
                "edate": node.get("edate"),
                "treeinfo_globalid": node.get("treeinfo_globalid", ""),
            })
        return results

    def find_cid_by_path(self, path: list[str], code: str = "1") -> str | None:
        pid = ""
        current = self.get_tree_children(pid, code)
        for segment in path:
            matched = [n for n in current if segment in n["name"]]
            if not matched:
                return None
            node = matched[0]
            if node["isLeaf"] or segment == path[-1]:
                return node["cid"]
            pid = node["cid"]
            current = self.get_tree_children(pid, code)
        return None

    def get_indicators(self, cid: str, use_cache: bool = True) -> list[dict]:
        cache_key = f"indicators_{cid}"
        if use_cache:
            cached = self._cache_get(cache_key, ttl=86400)
            if cached:
                return cached
        self._rate_limit()
        resp = self._session.get(
            f"{_NBS_BASE_URL}/new/queryIndicatorsByCid",
            params={"cid": cid},
            timeout=15,
        )
        data = resp.json()
        if not data.get("success"):
            return []
        indicators = data["data"].get("list", [])
        self._cache_set(cache_key, indicators)
        return indicators

    def find_indicator(self, cid: str, keyword: str, use_cache: bool = True) -> dict | None:
        indicators = self.get_indicators(cid, use_cache=use_cache)
        for ind in indicators:
            if keyword in ind.get("i_showname", ""):
                return ind
        return None

    def find_indicators(self, cid: str, keyword: str, use_cache: bool = True) -> list[dict]:
        indicators = self.get_indicators(cid, use_cache=use_cache)
        return [ind for ind in indicators if keyword in ind.get("i_showname", "")]

    def fetch_data(
            self,
            cid: str,
            indicator_ids: list[str],
            start: str = "2020",
            end: str = "",
            region: list[dict] | None = None,
            freq: str = "MM",
    ) -> pd.DataFrame:
        if region is None:
            region = [{"text": "全国", "value": "000000000000"}]
        if not end:
            end = datetime.now().strftime("%Y%m")
            if freq == "SS":
                yyyy = int(end[:4])
                q = (int(end[4:6]) - 1) // 3 + 1
                end = f"{yyyy}{q:02d}"
            elif freq == "YY":
                end = end[:4]
        suffix = {"MM": "MM", "SS": "SS", "YY": "YY"}.get(freq, "MM")
        if freq == "YY":
            dt_range = f"{start}{suffix}-{end}{suffix}"
        else:
            dt_range = f"{start}01{suffix}-{end}{suffix}"
        root_id = _NBS_ROOT_IDS.get({"MM": 1, "SS": 2, "YY": 3}.get(freq, 1), _NBS_ROOT_IDS[1])
        payload = {
            "cid": cid,
            "indicatorIds": indicator_ids,
            "das": region,
            "dts": [dt_range],
            "showType": "1",
            "rootId": root_id,
        }
        self._rate_limit()
        try:
            resp = self._session.post(
                f"{_NBS_BASE_URL}/stream/esData",
                json=payload,
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(f"NBS fetch_data HTTP {resp.status_code}, 返回空 DataFrame")
                return pd.DataFrame()
            data = resp.json()
        except (requests.exceptions.JSONDecodeError, ValueError) as e:
            logger.warning(f"NBS fetch_data JSON 解析失败: {e}, 返回空 DataFrame")
            return pd.DataFrame()
        if not data.get("success"):
            logger.warning(f"NBS API 失败: {data.get('message', '未知错误')}, 返回空 DataFrame")
            return pd.DataFrame()
        records = data.get("data", [])
        if not records:
            return pd.DataFrame()
        rows = []
        for rec in records:
            row = {"period": rec.get("code", ""), "period_name": rec.get("name", "")}
            for val in rec.get("values", []):
                col_name = val.get("i_showname", val.get("_id", ""))
                row[col_name] = val.get("value")
                if "i_mark" not in row and val.get("i_mark"):
                    row["_口径_"] = val["i_mark"]
            rows.append(row)
        df = pd.DataFrame(rows)
        for col in df.columns:
            if col in ("period", "period_name", "_口径_"):
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def fetch_merged(
            self,
            cid_indicator_pairs: list[tuple[str, str]],
            cid_date_ranges: list[tuple[str | None, str | None]] | None = None,
            start: str = "2000",
            end: str = "",
            freq: str = "MM",
    ) -> pd.DataFrame:
        all_frames = []
        for i, (cid, ind_id) in enumerate(cid_indicator_pairs):
            df = self.fetch_data(cid, [ind_id], start=start, end=end, freq=freq)
            if df is not None and not df.empty:
                val_cols = [c for c in df.columns if c not in ("period", "period_name", "_口径_")]
                if val_cols:
                    df = df[["period"] + val_cols]
                    sdate = cid_date_ranges[i][0] if cid_date_ranges else None
                    edate = cid_date_ranges[i][1] if cid_date_ranges else None
                    df["_sdate"] = sdate or ""
                    df["_edate"] = edate or ""
                    all_frames.append(df)
        if not all_frames:
            return pd.DataFrame()
        stacked = pd.concat(all_frames, ignore_index=True)
        val_col = [c for c in stacked.columns if c not in ("period", "_sdate", "_edate")][0]
        periods = sorted(stacked["period"].unique())
        rows = []
        for p in periods:
            subset = stacked[stacked["period"] == p]
            if subset.empty:
                continue
            candidates = []
            for _, row in subset.iterrows():
                v = row[val_col]
                if pd.isna(v):
                    continue
                sd = str(row["_sdate"]).strip()
                ed = str(row["_edate"]).strip()
                p_str = str(p)
                p_num = int(p_str[:4]) if p_str.endswith("YY") else int(p_str[:6])
                in_range = True
                if sd and sd != "None":
                    in_range = in_range and p_num >= int(sd.replace("-", "")[:6])
                if ed and ed != "None" and str(ed) != "None":
                    in_range = in_range and p_num <= int(ed.replace("-", "")[:6])
                candidates.append((v, in_range, sd, ed))
            if candidates:
                valid = [c for c in candidates if c[1]]
                if valid:
                    rows.append({"period": p, val_col: valid[-1][0]})
                else:
                    rows.append({"period": p, val_col: candidates[0][0]})
        result = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["period", val_col])
        return result

    def search_and_fetch(
            self,
            keyword: str,
            indicator_keyword: str = "增减",
            start: str = "2000",
            end: str = "",
            freq: str = "MM",
    ) -> pd.DataFrame | None:
        candidates = self.search(keyword, freq={"MM": "月度", "SS": "季度", "YY": "年度"}.get(freq, ""))
        if not candidates:
            return None
        cid_infos = []
        for c in candidates:
            indicators = self.get_indicators(c["cid"])
            matched = [i for i in indicators if indicator_keyword in (i.get("i_showname") or "")]
            if matched:
                cid_infos.append({
                    "cid": c["cid"],
                    "name": c["name"],
                    "sdate": c.get("sdate"),
                    "edate": c.get("edate"),
                    "indicator": matched[0],
                })
        if not cid_infos:
            return None

        def _sort_key(x):
            s = x.get("sdate")
            return int(s) if s else 9999

        cid_infos.sort(key=_sort_key)
        pairs = [(ci["cid"], ci["indicator"]["_id"]) for ci in cid_infos]
        date_ranges = [(ci.get("sdate"), ci.get("edate")) for ci in cid_infos]
        return self.fetch_merged(pairs, cid_date_ranges=date_ranges, start=start, end=end, freq=freq)

    def clear_cache(self):
        for f in self.cache_dir.glob("*.json"):
            f.unlink()

    def cache_size(self) -> int:
        return sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))


def _get_nbs_client():
    return _NbsClient()


def _clean_df(df) -> tuple[list[str], list[float]]:
    if df is None or df.empty:
        return [], []
    periods = [str(p)[:6] for p in df["period"].tolist()]
    # 排除非数值列（period / period_name / 口径标记），取第一个真实值列
    val_col = [c for c in df.columns if c not in ("period", "period_name", "_口径_")][0]
    values = df[val_col].tolist()
    clean_p, clean_v = [], []
    for p, v in zip(periods, values):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            # 缺失/非数值（"-" / None / 空串）→ 跳过该期，不计入序列
            continue
        if not np.isfinite(fv):
            continue
        clean_p.append(p)
        clean_v.append(fv)
    # 统一按时间升序，与 fetch_merged 输出契约一致，避免周期相位计算错位
    order = sorted(range(len(clean_p)), key=lambda i: clean_p[i])
    clean_p = [clean_p[i] for i in order]
    clean_v = [clean_v[i] for i in order]
    return clean_p, clean_v


def _fetch_by_indicator_name(
        dataset_keyword: str,
        indicator_name: str,
        freq: str = "MM",
        start: str = "2000",
) -> pd.DataFrame | None:
    client = _get_nbs_client()
    cids = client.search(dataset_keyword)
    if not cids:
        return None
    cid_infos = []
    for c in cids:
        indicators = client.get_indicators(c["cid"])
        for ind in indicators:
            name = ind.get("i_showname", "")
            if name == indicator_name or name.startswith(indicator_name):
                cid_infos.append({
                    "cid": c["cid"],
                    "name": c["name"],
                    "sdate": c.get("sdate"),
                    "edate": c.get("edate"),
                    "indicator": ind,
                })
                break
    if not cid_infos:
        return None
    cid_infos.sort(
        key=lambda x: int(x.get("sdate") or 0) if x.get("sdate") and x["sdate"].lstrip("-").isdigit() else 9999)
    pairs = [(ci["cid"], ci["indicator"]["_id"]) for ci in cid_infos]
    date_ranges = [(ci.get("sdate"), ci.get("edate")) for ci in cid_infos]
    return client.fetch_merged(pairs, cid_date_ranges=date_ranges, start=start, end="", freq=freq)


def _fetch_nbs_inventory_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("产成品存货", "增减"))


def _fetch_nbs_ind_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("规上工业增加值增长速度", "同比增长"))


def _fetch_nbs_fix_inv_monthly() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("固定资产投资概况", "累计增长"))


def _fetch_nbs_re_dev_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("房地产开发投资情况", "累计增长"))


def _fetch_nbs_cpi_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_fetch_by_indicator_name(
        "全国居民消费价格分类指数 (上年同月=100)",
        "居民消费价格指数 (上年同月=100)",
    ))


def _fetch_nbs_ppi_yoy() -> tuple[list[str], list[float]]:
    return _clean_df(_fetch_by_indicator_name(
        "工业生产者出厂价格指数 (上年同月=100)",
        "工业生产者出厂价格指数 (上年同月=100)",
    ))


def _fetch_nbs_gdp_quarterly() -> tuple[list[str], list[float]]:
    try:
        df = _fetch_by_indicator_name(
            "国内生产总值指数",
            "国内生产总值指数 (上年同期=100) 当季值",
            freq="SS",
        )
        if df is not None:
            val_col = [c for c in df.columns if c not in ("period",)][0]
            df[val_col] = df[val_col] - 100
        return _clean_df(df)
    except Exception:
        return [], []


def _fetch_nbs_unemployment() -> tuple[list[str], list[float]]:
    return _clean_df(_get_nbs_client().search_and_fetch("城镇调查失业率", "失业率"))


# 设备工器具购置固定资产投资（朱格拉周期核心指标）
# NBS 官方 data API 中该指标挂在「固定资产投资增速」月度节点下，
# 指标名为「设备工器具购置固定资产投资额累计增长 (%)」。
# cid / indicator_id 已固化（NBS 树节点 _id 稳定，不受分类层级微调影响）。
# 之前误判为「只有分行业/年度、需爬新闻稿」，实为全国月度汇总序列，直接走官方 API。
_EQUIP_INVEST_CID = "aac38c7aa152478ebea254ac412aa0a1"
_EQUIP_INVEST_IND = "59b2716c393f4861bfb30e244358005b"


def _fetch_nbs_equip_invest() -> tuple[list[str], list[float]]:
    """设备工器具购置固定资产投资（朱格拉周期核心指标）

    走 NBS 官方 data API（与 fix_inv / mfg / cap 同源），
    用固化的 (cid, indicator_id) 拉全国月度累计同比序列，无需关键词搜索、无需爬网页。
    """
    client = _get_nbs_client()
    df = client.fetch_data(
        _EQUIP_INVEST_CID, [_EQUIP_INVEST_IND], start="2000", end="", freq="MM"
    )
    return _clean_df(df)


def _fetch_nbs_manufacturing_invest() -> tuple[list[str], list[float]]:
    """制造业固定资产投资（朱格拉周期辅助指标）

    NBS 官方 data API 能提供历史序列（优先），新闻稿爬虫作兜底补齐最新期。
    """
    result = _clean_df(_get_nbs_client().search_and_fetch("分行业固定资产投资", "制造业固定资产投资额累计增长"))
    if result[0]:
        extra = _clean_df(_get_nbs_client().search_and_fetch("固定资产投资增速", "制造业固定资产投资额累计增长"))
        if extra[0]:
            p, v = result
            ep, ev = extra
            seen = set(p)
            for i, per in enumerate(ep):
                if per not in seen:
                    p.append(per)
                    v.append(ev[i])
            result = (p, v)
    if not result[0]:
        result = _manufacturing_from_release()
    return result


def _fetch_nbs_re_sales_area() -> tuple[list[str], list[float]]:
    """商品房销售面积（库兹涅茨周期核心指标）"""
    return _clean_df(_get_nbs_client().search_and_fetch("商品房销售面积", "增长"))


def _fetch_nbs_re_new_start() -> tuple[list[str], list[float]]:
    """房地产新开工施工面积累计增长（库兹涅茨周期核心指标）"""
    return _clean_df(_get_nbs_client().search_and_fetch("房地产施工、竣工面积", "新开工施工面积累计增长"))


def _fetch_nbs_capacity_util() -> tuple[list[str], list[float]]:
    """产能利用率（朱格拉周期辅助信号）

    NBS 官方 data API 能提供历史季度序列（优先），新闻稿爬虫作兜底补齐最新期。
    """
    periods, values = _clean_df(_get_nbs_client().search_and_fetch(
        "工业产能利用率", "产能利用率", freq="SS", start="2021"
    ))
    if not periods:
        periods, values = _capacity_util_from_release()
    return periods, values


# ── 朱格拉指标兜底：国家统计局新闻稿爬虫（仅制造业/产能利用率，best-effort）──
# equipment_yoy 已改为直接走官方 data API（固化 cid+indicator_id，见 _EQUIP_INVEST_*）。
# 以下的爬虫仅作为 mfg / capacity_util 的兜底补齐（官方 API 优先，爬不到也不致命）。
from .scrapers.nbs_release_scraper import (  # noqa: E402
    collect_equip_mfg_history,
    collect_capacity_util_history,
)


# 爬虫结果缓存（避免 eng.run 重复启动 playwright + 保证两次调用一致性）
_RELEASE_CACHE: dict = {}


def _cached_release(key: str, fn):
    import time
    cached = _RELEASE_CACHE.get(key)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    result = fn()
    _RELEASE_CACHE[key] = (time.time(), result)
    return result


def _manufacturing_from_release() -> tuple[list[str], list[float]]:
    """制造业固投：爬新闻稿历史月度序列，upsert 进 cycle_db 后返回完整序列。"""
    def _do():
        try:
            periods, _, mfgs = collect_equip_mfg_history()
        except Exception as e:
            logger.warning(f"制造业固投新闻稿抓取失败: {e}")
            return [], []
        if not periods:
            return [], []
        try:
            from deep_fusion.shared.cycle_db import upsert
            upsert("manufacturing_yoy", periods, [v for v in mfgs])
        except Exception as e:
            logger.warning(f"upsert manufacturing_yoy 失败: {e}")
        return periods, [v for v in mfgs]
    return _cached_release("manufacturing_yoy", _do)


def _capacity_util_from_release() -> tuple[list[str], list[float]]:
    """产能利用率：爬新闻稿历史季度序列，upsert 进 cycle_db 后返回完整序列。"""
    def _do():
        try:
            periods, values = collect_capacity_util_history()
        except Exception as e:
            logger.warning(f"产能利用率新闻稿抓取失败: {e}")
            return [], []
        if not periods:
            return [], []
        try:
            from deep_fusion.shared.cycle_db import upsert
            upsert("capacity_util", periods, [v for v in values])
        except Exception as e:
            logger.warning(f"upsert capacity_util 失败: {e}")
        return periods, [v for v in values]
    return _cached_release("capacity_util", _do)


def _fetch_house_price_yoy() -> tuple[list[str], list[float]]:
    """70城新建商品住宅价格同比（库兹涅茨周期主判定信号）"""
    import os
    old_http = os.environ.pop("HTTP_PROXY", None)
    old_https = os.environ.pop("HTTPS_PROXY", None)
    old_all = os.environ.pop("ALL_PROXY", None)
    old_socks = os.environ.pop("SOCKS_PROXY", None)
    _ = os.environ.pop("all_proxy", None)
    _ = os.environ.pop("https_proxy", None)
    _ = os.environ.pop("http_proxy", None)
    _ = os.environ.pop("socks_proxy", None)
    try:
        import akshare as ak
        cities = [("北京", "上海"), ("广州", "深圳"), ("杭州", "成都"), ("武汉", "南京"), ("天津", "重庆")]
        all_data: dict[str, list[float]] = {}
        for c1, c2 in cities:
            df = ak.macro_china_new_house_price(city_first=c1, city_second=c2)
            if df is None or df.empty:
                continue
            for _, r in df.iterrows():
                d = str(r.iloc[0])[:7].replace("-", "")
                v = r.get("新建商品住宅价格指数-同比")
                if v is None or pd.isna(v):
                    continue
                if d not in all_data:
                    all_data[d] = []
                all_data[d].append(float(v))
        if not all_data:
            return [], []
        periods = sorted(all_data.keys())
        values = [round(sum(all_data[p]) / len(all_data[p]), 2) for p in periods]
        return periods, values
    except Exception as e:
        logger.warning(f"70城房价获取失败: {e}")
        return [], []
    finally:
        if old_http:
            os.environ["HTTP_PROXY"] = old_http
        if old_https:
            os.environ["HTTPS_PROXY"] = old_https
        if old_all:
            os.environ["ALL_PROXY"] = old_all
        if old_socks:
            os.environ["SOCKS_PROXY"] = old_socks


# ── 实物产品产量（接口预留，NBS API 产品级访问暂受限）────


def _fetch_product_steel() -> tuple[list[str], list[float]]:
    """粗钢产量（万吨），NBS 季度/月度数据"""
    # TODO: NBS API 恢复后接入正式数据
    # cid_monthly = "b92d3048917a4a72bb1c3e7592e70f28"
    # indicator_id = "..."  # 粗钢销售量累计值
    logger.warning("粗钢产量: NBS 产品级 API 暂不可用")
    return [], []


def _fetch_product_cement() -> tuple[list[str], list[float]]:
    """水泥产量（万吨），月度数据"""
    logger.warning("水泥产量: NBS 产品级 API 暂不可用")
    return [], []


def _fetch_product_steel_prod() -> tuple[list[str], list[float]]:
    """钢材产量（万吨）"""
    logger.warning("钢材产量: NBS 产品级 API 暂不可用")
    return [], []


def _fetch_product_coal() -> tuple[list[str], list[float]]:
    """原煤产量（万吨）"""
    logger.warning("原煤产量: NBS 产品级 API 暂不可用")
    return [], []


def _fetch_product_electricity() -> tuple[list[str], list[float]]:
    """发电量（亿千瓦时）"""
    logger.warning("发电量: NBS 产品级 API 暂不可用")
    return [], []

# ═══════════════════════════════════════════════════════════════
# Kondratiev 可选算法
