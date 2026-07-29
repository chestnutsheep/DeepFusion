"""limit_up_scan 网络无关单测：锁定 _recent_trade_dates 的交易日解析修复。

背景（2026-07-29）：akshare 的 tool_trade_date_hist_sina 返回的 trade_date 列是
object 类型（datetime.date 对象），原代码用 df["trade_date"].dt.strftime(...) 对
object 列会抛 AttributeError（被 except 吞掉 → 返回 []），导致连板高度回溯失败、
全部判为连板1。修复用 pd.to_datetime 先转换，并在文件顶部补 import pandas as pd。
"""
import pandas as pd
from datetime import date, timedelta
from unittest.mock import patch


def _make_df(dates):
    """构造 object 列（datetime.date 对象），复现 sina 真实返回。"""
    return pd.DataFrame({"trade_date": list(dates)})


def test_recent_trade_dates_object_dtype_and_future_filter():
    from deep_fusion.tools import limit_up

    today = date.today()
    past = [today - timedelta(days=k) for k in (20, 10, 5, 2, 1)]
    future = [today + timedelta(days=k) for k in (1, 30, 200)]  # 未来占位日期
    df = _make_df(past + future)

    with patch.object(limit_up, "ak_cache", return_value=df):
        res = limit_up._recent_trade_dates(6)

    expected = sorted(d.strftime("%Y%m%d") for d in past)[-6:]
    assert res == expected                      # 取最近 6 个、升序、YYYYMMDD
    assert all(x <= today.strftime("%Y%m%d") for x in res)
    assert (today + timedelta(days=1)).strftime("%Y%m%d") not in res  # 未来被过滤


def test_recent_trade_dates_none_and_empty():
    from deep_fusion.tools import limit_up

    with patch.object(limit_up, "ak_cache", return_value=None):
        assert limit_up._recent_trade_dates(6) == []

    with patch.object(limit_up, "ak_cache", return_value=pd.DataFrame({"trade_date": []})):
        assert limit_up._recent_trade_dates(6) == []


def test_recent_trade_dates_exact_count_when_few():
    from deep_fusion.tools import limit_up

    today = date.today()
    few = [today - timedelta(days=k) for k in (3, 2, 1, 0)]
    df = _make_df(few)
    with patch.object(limit_up, "ak_cache", return_value=df):
        res = limit_up._recent_trade_dates(6)
    assert res == sorted(d.strftime("%Y%m%d") for d in few)  # 不足 n 个时返回全部
