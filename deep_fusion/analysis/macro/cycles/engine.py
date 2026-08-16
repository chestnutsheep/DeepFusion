"""Cycle engine: shared helpers + CycleConfig + CycleEngine"""

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from ....shared.spectral import cf_bandpass

logger = logging.getLogger(__name__)


def _zscore(values: list[float | None]) -> list[float | None]:
    """Z-score 标准化"""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return values
    m, s = float(np.mean(clean)), float(np.std(clean))
    if s < 1e-12:
        return values
    return [None if v is None else round((v - m) / s, 4) for v in values]


def _institutional_preprocess(values: list[float | None], low_yr: float, high_yr: float, fs: float) -> list[
    float | None]:
    """机构标准预处理: 带通滤波 → Z-score"""
    clean = [v for v in values if v is not None]
    if len(clean) < 10:
        return _zscore(values)
    try:
        bp = cf_bandpass(clean, low_yr=low_yr, high_yr=high_yr, ma_yr=None, fs=fs)
        zs = bp["zscore"]
        i = 0
        result: list[float | None] = []
        for v in values:
            if v is not None:
                result.append(round(zs[i], 4) if i < len(zs) else None)
                i += 1
            else:
                result.append(None)
        return result
    except Exception:
        return _zscore(values)


def _direction(cur: float | None, prev: float | None) -> int | None:
    if cur is None or prev is None:
        return None
    return 1 if cur > prev else (-1 if cur < prev else 0)


def _ma(values: list[float | None], window: int = 3) -> list[float | None]:
    result = []
    for i, v in enumerate(values):
        if v is None:
            result.append(None)
            continue
        w = [values[j] for j in range(max(0, i - window + 1), i + 1) if values[j] is not None]
        if len(w) >= 2:
            result.append(round(sum(w) / len(w), 2))
        else:
            result.append(v)
    return result


def _to_period(raw: str) -> str:
    """统一解析 akshare 日期格式 → YYYYMM"""
    s = raw.replace("年", "").replace("月", "").replace("日", "").replace("-", "").replace("/", "").strip()
    if len(s) >= 6:
        return s[:6]
    if len(s) == 4:
        return s + "01"
    return raw[:6]


def _parse_ak(df, val_col: str = "", date_col: str = "日期") -> tuple[list[str], list[float]]:
    if df is None or df.empty:
        return [], []
    if date_col not in df.columns:
        for c in df.columns:
            if "月" in str(c) and "日" not in str(c):
                date_col = c
                break
    if not val_col or val_col not in df.columns:
        for c in df.columns:
            if c == date_col:
                continue
            try:
                float(df[c].dropna().iloc[0])
                val_col = c
                break
            except (ValueError, IndexError):
                continue
    periods, values = [], []
    for _, r in df.iterrows():
        raw = str(r.get(date_col, ""))
        v = r.get(val_col)
        if v is None:
            continue
        try:
            fv = float(v)
            if not np.isfinite(fv):
                continue
        except (ValueError, TypeError):
            continue
        periods.append(_to_period(raw))
        values.append(fv)
    return periods, values


def _fmt(v: float | None) -> str:
    return f"{v:>6.2f}" if v is not None else "  N/A"


def _arr(d: int | None) -> str:
    return "↑" if d == 1 else ("↓" if d == -1 else "—")


def _p2date(period: str):
    from datetime import date
    return date(int(period[:4]), int(period[4:6]), 1)


def _ak_safe(name, col, fallback=None):
    try:
        fn = getattr(ak, name, None)
        if fn is None:
            return pd.DataFrame(), col
        df = ak_cache(fn, ttl=86400)
        return (df, col) if df is not None else (pd.DataFrame(), col)
    except Exception:
        return pd.DataFrame(), col


# ── 周期引擎 ──────────────────────────────────────────────

@dataclass
class IndicatorDef:
    key: str  # 存到 data 字典的 key
    fetch_fn: Callable | None = None  # 无参函数 → (periods, values)
    akshare_fn: str | None = None  # akshare 函数名
    akshare_col: str | None = None  # 从 DataFrame 取的列（留空自动检测）
    _cache: tuple | None = field(default=None, repr=False)

    def fetch(self) -> tuple[list[str], list[float]]:
        if self._cache is not None:
            return self._cache
        if self.fetch_fn:
            self._cache = self.fetch_fn()
        elif self.akshare_fn:
            # DB-first + 增量更新：
            # 原始数据(Actual)永不过期，但检查是否有新数据可追加
            from ....shared.cycle_db import get as db_get, upsert as db_set
            from ....shared.cycle_db import get_latest_date, append as db_append
            from ....shared.freshness import needs_incremental_update

            db_data = db_get(self.key)
            if db_data is not None and not db_data.empty:
                db_latest = get_latest_date(self.key)
                # 检查是否需要增量更新
                if needs_incremental_update(self.key, db_latest):
                    try:
                        df, col = _ak_safe(self.akshare_fn, self.akshare_col or "")
                        new_periods, new_values = _parse_ak(df, col)
                        if new_periods:
                            added = db_append(self.key, new_periods, new_values)
                            if added > 0:
                                logger.info("IndicatorDef.fetch: %s 增量追加 %d 行 (DB最新=%s)",
                                            self.key, added, db_latest)
                                # 重新读取更新后的 DB 数据
                                db_data = db_get(self.key)
                    except Exception as e:
                        logger.warning("IndicatorDef.fetch: %s 增量更新失败: %s, 使用DB旧数据",
                                       self.key, e)
                # 返回 DB 数据（可能已增量更新）
                dates = db_data["date"].astype(str).tolist()
                vals = [float(v) if v is not None else None for v in db_data["value"]]
                self._cache = dates, vals
                return self._cache
            # DB 无数据，走 akshare 全量拉取
            df, col = _ak_safe(self.akshare_fn, self.akshare_col or "")
            periods, values = _parse_ak(df, col)
            if periods:
                try:
                    db_set(self.key, periods, values)
                except Exception:
                    pass
            self._cache = periods, values
        else:
            self._cache = [], []
        return self._cache


@dataclass
class CycleConfig:
    id: str
    name: str
    desc: str
    indicators: list[IndicatorDef]
    core_key: str  # 必须存在的 key → 用于过滤 period
    requires: list[str] | None = None  # 额外的必须字段（如 Kitchin 需要 demand_yoy+inventory_yoy）
    ma_window: int = 3
    classify_fn: Callable | None = None
    phase_names: dict | None = None


class CycleEngine:
    """配置驱动的周期计算引擎，替代 N 份 _compute_* 函数"""

    def __init__(self, config: CycleConfig):
        self.cfg = config
        self.data: dict[str, dict] = {}
        self.periods: list[str] = []
        self.results: list[dict] = []

    def run(self, limit: int = 60) -> tuple[list[str], dict, list[dict]]:
        self.data = {}
        all_periods: set[str] = set()

        for ind in self.cfg.indicators:
            periods, values = ind.fetch()
            all_periods.update(periods)

        all_p = sorted(all_periods)
        for p in all_p:
            entry: dict = {}
            for ind in self.cfg.indicators:
                periods, values = ind.fetch()
                try:
                    entry[ind.key] = values[periods.index(p)]
                except ValueError:
                    pass
            self.data[p] = entry

        req = (self.cfg.requires or []) + [self.cfg.core_key]
        self.periods = [p for p in all_p if all(k in self.data[p] for k in req)]
        if limit > 0:
            self.periods = self.periods[-limit:]
        if len(self.periods) < 6:
            self.periods, self.data, self.results = [], {}, []
            return self.periods, self.data, self.results

        if self.cfg.classify_fn:
            self.results = self.cfg.classify_fn(self.periods, self.data, self.cfg)

        return self.periods, self.data, self.results

# ── 阶段判定函数（各周期专属） ──────────────────────────
