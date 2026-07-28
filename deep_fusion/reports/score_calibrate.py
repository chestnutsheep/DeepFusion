"""连板评分实证校准脚本（量化分析师协作：自动优化项目设计）。

用途：用 akshare 真实涨停股池数据，对 score.py 的 8 因子做实证校准——
  1) 构建「次日连板延续」标签（连板高度回溯方法：跨交易日追踪 连板数）；
  2) 逐因子算 AUC / 分组成功率，量化每个因子的区分力；
  3) 以 AUC 归一化重赋权，输出 data-driven 权重建议（替代初版启发式权重）。

运行（需联网 + 代理，akshare 直连）：
  venv/bin/python -m deep_fusion.reports.score_calibrate --days 40 --out data/score_calibration.json

输出：打印校准报告，并写 JSON（含 recommended_weights / factor_stats / base_rate / n）。

注意：
- 量比/振幅需日K（逐只拉取成本高），本脚本仅用涨停池直接可得的 5 个因子
  （换手率/流通市值/封单比/封板时间/连板数）做权重校准；量比/振幅权重维持初版，
  后续可单独用日K批量校准。
- 标签为「连板延续」(短线情绪博弈)，非「中长期收益」，对应 score 的设计目标。
"""
import argparse
import datetime
import json
import os
import time

import pandas as pd

try:
    import akshare as ak
except Exception:
    ak = None


def _auc(y, x):
    """无依赖 AUC（Mann-Whitney）。y:0/1, x:连续。缺失成对丢弃。"""
    pairs = [(y[i], x[i]) for i in range(len(y)) if x[i] is not None]
    pos = [v for yy, v in pairs if yy == 1]
    neg = [v for yy, v in pairs if yy == 0]
    if not pos or not neg:
        return None
    c = n = 0
    for a in pos:
        for b in neg:
            c += 1 if a > b else (0.5 if a == b else 0)
            n += 1
    return c / n if n else None


def _collect_labeled(days=40):
    """拉取最近 days 个交易日的涨停池，构造 (features, label) 样本。"""
    if ak is None:
        raise RuntimeError("akshare 不可用")
    cal = ak.tool_trade_date_hist_sina()
    td = cal["trade_date"]
    try:
        tdates = sorted(pd.to_datetime(td).dt.strftime("%Y%m%d").tolist())
    except Exception:
        tdates = sorted(td.astype(str).str.replace("-", "").tolist())
    # 日历常延伸到未来(占位数据)，只保留 <= 今天的真实交易日
    today = datetime.date.today().strftime("%Y%m%d")
    tdates = [d for d in tdates if d <= today][-days - 1:]
    pools = {}
    for d in tdates:
        try:
            df = ak.stock_zt_pool_em(date=d)
        except Exception:
            df = None
        time.sleep(0.3)
        if df is None or df.empty:
            pools[d] = {}
            continue
        pools[d] = {str(r["代码"]): r for _, r in df.iterrows()}

    rows = []
    for i, d in enumerate(tdates[:-1]):
        nxt = tdates[i + 1]
        p0, p1 = pools[d], pools[nxt]
        for code, r in p0.items():
            bh = _f(r.get("连板数"))
            if bh is None:
                continue
            # 标签：次日仍涨停且连板数+1
            r1 = p1.get(code)
            success = r1 is not None and (_f(r1.get("连板数")) or 0) >= bh + 1
            t = _f(r.get("换手率"))
            mv = _f(r.get("流通市值"))            # 元
            seal = _f(r.get("封板资金"))          # 元
            st = r.get("最后封板时间") or r.get("封板时间")  # HHMMSS
            rows.append({
                "code": code, "date": d, "board_height": bh,
                "turnover": t,
                "float_mv_yi": (mv / 1e8) if mv is not None else None,   # →亿元
                "seal_ratio": ((seal / 1e4) / (mv / 1e8 * 10000) * 100) if (seal and mv) else None,  # →%
                "seal_time_min": _seal_min(st),
                "label": 1 if success else 0,
            })
    return rows


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _seal_min(ts):
    if not ts:
        return None
    s = str(ts).strip()
    if ":" in s:
        p = s.split(":")
        try:
            return int(p[0]) * 60 + int(p[1])
        except Exception:
            return None
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) >= 4:
        try:
            return int(digits[:2]) * 60 + int(digits[2:4])
        except Exception:
            return None
    return None


def _bucket_seal(m):
    if m is None:
        return "无数据"
    if m <= 10 * 60 + 30:
        return "早盘(≤10:30)"
    if m <= 14 * 60:
        return "午后(10:30-14:00)"
    return "尾盘(>14:00)"


def calibrate(rows):
    n = len(rows)
    base = sum(r["label"] for r in rows) / n if n else 0.0
    # 连续因子 AUC
    cont = {
        "换手率": [r["turnover"] for r in rows],
        "流通市值(亿)": [r["float_mv_yi"] for r in rows],
        "封单比(%)": [r["seal_ratio"] for r in rows],
    }
    y = [r["label"] for r in rows]
    factor_auc = {}
    for name, xs in cont.items():
        a = _auc(y, xs)
        factor_auc[name] = round(a, 3) if a is not None else None

    # 封板时间 分组成功率
    seal_groups = {}
    for r in rows:
        g = _bucket_seal(r["seal_time_min"])
        seal_groups.setdefault(g, [0, 0])
        seal_groups[g][0] += r["label"]
        seal_groups[g][1] += 1
    seal_rate = {g: (v[0] / v[1] if v[1] else 0) for g, v in seal_groups.items()}

    # 连板数 分组成功率（连板高度回溯的辅助证据）
    bh_groups = {}
    for r in rows:
        g = r["board_height"]
        bh_groups.setdefault(g, [0, 0])
        bh_groups[g][0] += r["label"]
        bh_groups[g][1] += 1
    bh_rate = {g: (v[0] / v[1] if v[1] else 0) for g, v in bh_groups.items()}

    # 权重建议：以 AUC 区分力归一化（仅对池内可得因子），量比/振幅维持初版
    auc_map = {
        "换手率": factor_auc.get("换手率"),
        "流通市值": factor_auc.get("流通市值(亿)"),
        "封单比": factor_auc.get("封单比(%)"),
        "封板时间": None,  # 用分组成功率代替 AUC
    }
    # 封板时间 AUC（用分钟连续值）
    auc_map["封板时间"] = _auc(y, [r["seal_time_min"] for r in rows])
    # 连板数 AUC（连续值）
    auc_map["连板数"] = _auc(y, [r["board_height"] for r in rows])

    # 区分力分 = max(0, |AUC-0.5|*2) ∈ [0,1]
    disc = {k: (max(0, abs(v - 0.5) * 2) if v is not None else 0.0) for k, v in auc_map.items()}
    # 初版权重中可由数据驱动的因子
    base_w = {"换手率": 20, "封板时间": 14, "流通市值": 10, "封单比": 10,
              "量比": 12, "二板缩量": 18, "振幅": 10, "题材热度": 6}
    drivable = ["换手率", "封板时间", "流通市值", "封单比"]
    nondrv = ["量比", "二板缩量", "振幅", "题材热度"]
    s = sum(disc[k] for k in drivable) or 1.0
    rec = {}
    for k in drivable:
        rec[k] = round(base_w[k] * (0.4 + 0.6 * disc[k] / s) * (s / sum(base_w[kk] for kk in drivable)) , 1)
    # 归一化驱动因子到原初版驱动权重和
    tot_drv_base = sum(base_w[k] for k in drivable)
    tot_rec = sum(rec.values()) or 1.0
    rec = {k: round(v * tot_drv_base / tot_rec, 1) for k, v in rec.items()}
    for k in nondrv:
        rec[k] = base_w[k]
    # 四舍五入修正到和为100
    diff = round(100 - sum(rec.values()), 1)
    rec["换手率"] = round(rec["换手率"] + diff, 1)

    return {
        "n": n, "base_rate": round(base, 3),
        "factor_auc": {k: (round(v, 3) if v is not None else None) for k, v in factor_auc.items()},
        "seal_time_auc": round(auc_map["封板时间"], 3) if auc_map["封板时间"] else None,
        "board_height_auc": round(auc_map["连板数"], 3) if auc_map["连板数"] else None,
        "seal_time_rate": {k: round(v, 3) for k, v in seal_rate.items()},
        "board_height_rate": {str(k): round(v, 3) for k, v in bh_rate.items()},
        "disc_power": {k: round(v, 3) for k, v in disc.items()},
        "recommended_weights": rec,
        "initial_weights": base_w,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=40)
    p.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "data", "score_calibration.json"))
    args = p.parse_args()
    print(f"拉取最近 {args.days} 个交易日涨停池并构造标签 ...")
    rows = _collect_labeled(args.days)
    print(f"样本量 n={len(rows)}")
    if not rows:
        print("无样本（可能联网失败或非交易数据缺失），退出。")
        return
    rep = calibrate(rows)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
