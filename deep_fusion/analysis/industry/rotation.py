"""Industry rotation analysis: momentum ranking, relative strength, capital flow."""
import akshare as ak
import pandas as pd

from ...shared.utils import ak_cache


def sector_momentum(board: str = "东方财富", top_n: int = 10) -> list[dict]:
    """Rank sectors by short-term momentum (5-day price change).

    Args:
        board: 板块分类（东方财富/申万）
        top_n: 返回前 N 名

    Returns:
        list[dict]: [{name, change_pct, volume, turnover, momentum_score}, ...]
    """
    spot = ak_cache(ak.stock_board_industry_spot_em, ttl=300, ttl2=600)
    if spot is None or spot.empty:
        return []

    required = ["板块名称", "涨跌幅"]
    for c in required:
        if c not in spot.columns:
            return []

    df = spot.copy()
    df["动量得分"] = df["涨跌幅"].rank(pct=True)
    if "成交额" in df.columns:
        df["成交额(亿)"] = df["成交额"] / 1e8
    if "换手率" in df.columns:
        df["换手率"] = df["换手率"]

    cols = ["板块名称", "涨跌幅"]
    rename = {"板块名称": "name", "涨跌幅": "change_pct"}
    if "成交额(亿)" in df.columns:
        cols.append("成交额(亿)")
        rename["成交额(亿)"] = "volume_bn"
    if "换手率" in df.columns:
        cols.append("换手率")
        rename["换手率"] = "turnover"
    rename["动量得分"] = "momentum_score"
    cols.append("动量得分")

    result = df.nlargest(top_n, "涨跌幅")[cols].rename(columns=rename)
    return result.to_dict("records")


def sector_rotation_matrix(top_n: int = 10) -> str:
    """Build a sector rotation matrix: momentum vs valuation quadrant.

    Returns:
        str: formatted CSV with [leading, improving, lagging, declining] labels
    """
    import akshare as ak

    spot = ak_cache(ak.stock_board_industry_spot_em, ttl=300, ttl2=600)
    if spot is None or spot.empty:
        return "数据不足"

    df = spot.copy()
    if "涨跌幅" not in df.columns or "板块名称" not in df.columns:
        return "缺少涨跌幅或板块名称列"

    # Label by momentum quantile
    q = df["涨跌幅"].rank(pct=True)
    df["象限"] = pd.cut(
        q,
        bins=[-0.01, 0.25, 0.5, 0.75, 1.01],
        labels=["declining", "lagging", "improving", "leading"],
    )

    cols = ["板块名称", "涨跌幅", "象限"]
    if "成交额" in df.columns:
        df["成交额(亿)"] = df["成交额"] / 1e8
        cols.append("成交额(亿)")
    if "换手率" in df.columns:
        cols.append("换手率")

    result = df.nlargest(top_n, "涨跌幅")[cols]
    return result.to_csv(index=False, float_format="%.2f")


def capital_flow_ranking(top_n: int = 20) -> str:
    """Rank sectors by net capital flow (主力净流入).

    Returns:
        str: formatted CSV
    """
    flow = ak_cache(ak.stock_fund_flow_industry, ttl=300, ttl2=600)
    if flow is None or flow.empty:
        return "数据不足"

    out = flow.head(top_n).to_csv(index=False, float_format="%.2f")
    return out
