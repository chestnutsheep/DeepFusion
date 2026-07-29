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

try:
    from deep_fusion.reports import score as _scoremod
except Exception:
    _scoremod = None
if _scoremod is None:
    # 兜底：直接按文件加载 score.py，避免触发 deep_fusion 包 __init__（fastmcp 等重依赖）
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "deep_fusion_reports_score",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "score.py"),
        )
        _scoremod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_scoremod)
    except Exception:
        _scoremod = None


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


def _row_item_scores(r):
    """把 _collect_labeled 的 row 映射为 score.py 各项打分 (name -> score)。
    仅用涨停池直接可得因子；量比/振幅/二板缩量/题材热度因取数成本未收集，跳过。
    """
    if _scoremod is None:
        return {}
    sm = r.get("seal_time_min")
    seal_ts = f"{sm // 60:02d}:{sm % 60:02d}" if sm is not None else None
    fmv = r.get("float_mv_yi")
    sr = r.get("seal_ratio")
    seal_amount = (sr / 100.0 * fmv * 10000.0) if (sr is not None and fmv) else None
    out = {}
    out["换手率"] = _scoremod._score_turnover(r.get("turnover"))[0]
    out["封板时间"] = _scoremod._score_seal_time(seal_ts)[0]
    out["流通市值"] = _scoremod._score_float_mv(fmv)[0]
    if seal_amount is not None and fmv:
        out["封单比"] = _scoremod._score_seal_ratio(seal_amount, fmv)[0]
    return out


def fit_platt(rows, weights=None):
    """对可得因子加权分做 Platt scaling，拟合 p = 1/(1+exp(A*score+B))。
    返回 {A, B, k, score_mid, brier, n}。

    注意：score 为可得因子子集的代理分（量比/振幅/二板缩量/题材热度因取数成本
    未纳入），A/B 应随日K批量校准（纳入量比/振幅）后升级。k=-A，score_mid=-B/A
    为逻辑中点（对应 p=0.5）。
    """
    import math
    wmap = weights or {"换手率": 18.0, "封板时间": 18.0, "流通市值": 9.0, "封单比": 9.0}
    xs, ys = [], []
    for r in rows:
        items = _row_item_scores(r)
        num = den = 0.0
        for name, sc in items.items():
            wt = wmap.get(name)
            if wt is None:
                continue
            num += sc * wt
            den += wt
        if den == 0:
            continue
        xs.append(num / den)
        ys.append(r["label"])
    if len(xs) < 10:
        return None
    # 单变量 logistic 回归：Newton-Raphson
    A, B = 0.0, 0.0
    for _ in range(200):
        gA = gB = hAA = hBB = hAB = 0.0
        for x, y in zip(xs, ys):
            z = A * x + B
            p = 1.0 / (1.0 + math.exp(-z)) if z > -700 else (1.0 if z >= 0 else 0.0)
            gA += (p - y) * x
            gB += (p - y)
            hAA += p * (1 - p) * x * x
            hBB += p * (1 - p)
            hAB += p * (1 - p) * x
        det = hAA * hBB - hAB * hAB
        if abs(det) < 1e-12:
            break
        dA = (gA * hBB - gB * hAB) / det
        dB = (hAA * gB - hAB * gA) / det
        A -= dA
        B -= dB
        if abs(dA) < 1e-7 and abs(dB) < 1e-7:
            break
    brier = 0.0
    for x, y in zip(xs, ys):
        z = A * x + B
        p = 1.0 / (1.0 + math.exp(-z)) if z > -700 else (1.0 if z >= 0 else 0.0)
        brier += (p - y) ** 2
    brier /= len(xs)
    k = -A
    score_mid = (-B / A) if abs(A) > 1e-9 else 50.0
    return {
        "A": round(A, 5), "B": round(B, 5), "k": round(k, 5),
        "score_mid": round(score_mid, 2), "brier": round(brier, 4), "n": len(xs),
    }


def per_item_hit_rate(rows):
    """对可得因子/连板数，按 tercile 算连板延续率，供贝叶斯似然。
    返回 {factor: {top_rate, mid_rate, bot_rate, auc}}。
    """
    if not rows:
        return {}
    y = [r["label"] for r in rows]
    cols = {
        "换手率": [r.get("turnover") for r in rows],
        "流通市值(亿)": [r.get("float_mv_yi") for r in rows],
        "封单比(%)": [r.get("seal_ratio") for r in rows],
        "封板时间(分)": [r.get("seal_time_min") for r in rows],
        "连板数": [r.get("board_height") for r in rows],
    }
    res = {}
    for name, xs in cols.items():
        pairs = [(yy, xx) for yy, xx in zip(y, xs) if xx is not None]
        if len(pairs) < 10:
            continue
        ys_p, xs_p = zip(*pairs)
        xs_p = list(xs_p)
        n = len(xs_p)
        q1 = sorted(xs_p)[n // 3]
        q2 = sorted(xs_p)[2 * n // 3]
        top = [yy for yy, xx in pairs if xx >= q2]
        mid = [yy for yy, xx in pairs if q1 <= xx < q2]
        bot = [yy for yy, xx in pairs if xx < q1]
        res[name] = {
            "top_rate": round(sum(top) / len(top), 3) if top else None,
            "mid_rate": round(sum(mid) / len(mid), 3) if mid else None,
            "bot_rate": round(sum(bot) / len(bot), 3) if bot else None,
            "auc": round(_auc(ys_p, xs_p), 3),
            # 三分位边界（原始单位），供接线层按个股真实值判档取 hit_rate
            "q1": round(q1, 4),
            "q2": round(q2, 4),
        }
    return res


def fit_posterior(rows, calib):
    """对 §E naive 贝叶斯 posterior 做 logistic 再校准（Platt scaling on posterior）。

    动机：§E 把 4 个因子按条件独立连乘似然比，但封单比/封板时间/流通市值/换手率高度
    同源（早封板往往同时高封单比、小流通、低换手），重复计数使强股 posterior 冲到
    0.7+（单因子 top 命中率仅 0.24–0.29）。本函数把样本上算出的 naive posterior z 作为
    特征，拟合 p = 1/(1+exp(A*logit(z)+B))，压缩到经验续板率。

    返回 {A, B, brier_naive, brier_cal, n}。brier_naive = 原 posterior 的 Brier（应偏高），
    brier_cal = 再校准后的 Brier（应下降）。
    """
    import math
    if _scoremod is None or not calib:
        return {}
    xs, ys = [], []
    for r in rows:
        m = r.get("seal_time_min")
        fmv = r.get("float_mv_yi")
        sr = r.get("seal_ratio")
        if m is None or fmv is None or sr is None:
            continue
        feats = {
            "board_height": r.get("board_height"),
            "turnover_1": r.get("turnover"),
            "seal_time": f"{int(m) // 60:02d}:{int(m) % 60:02d}",
            "seal_amount": sr / 100.0 * fmv * 10000.0,  # 还原万元，使 _seal_ratio_pct 回得 seal_ratio
            "float_mv": fmv,
            "sectors": r.get("sectors") or [],
        }
        try:
            res = _scoremod.calibrated_probability(feats, calib, proxy_score=None)
        except Exception:
            continue
        z = res.get("prob")
        if z is None or z <= 0 or z >= 1:
            continue
        xs.append(math.log(z / (1.0 - z)))
        ys.append(r["label"])
    if len(xs) < 10:
        return {}
    # Newton-Raphson 单变量 logistic
    A, B = 0.0, 0.0
    for _ in range(200):
        gA = gB = hAA = hBB = hAB = 0.0
        for x, y in zip(xs, ys):
            z = A * x + B
            p = 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0
            gA += (p - y) * x
            gB += (p - y)
            hAA += p * (1 - p) * x * x
            hBB += p * (1 - p)
            hAB += p * (1 - p) * x
        det = hAA * hBB - hAB * hAB
        if abs(det) < 1e-12:
            break
        dA = (gA * hBB - gB * hAB) / det
        dB = (hAA * gB - hAB * gA) / det
        A -= dA
        B -= dB
        if abs(dA) < 1e-7 and abs(dB) < 1e-7:
            break
    brier_naive = brier_cal = 0.0
    for x, y in zip(xs, ys):
        pn = 1.0 / (1.0 + math.exp(-x))  # = z
        brier_naive += (pn - y) ** 2
        z = A * x + B
        pc = 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0
        brier_cal += (pc - y) ** 2
    brier_naive /= len(xs)
    brier_cal /= len(xs)
    return {
        "A": round(A, 4), "B": round(B, 4),
        "brier_naive": round(brier_naive, 4), "brier_cal": round(brier_cal, 4),
        "n": len(xs),
    }


def _recalibrate(z, pf):
    """§E-2 再校准：p = 1/(1+exp(A*logit(z)+B))。与 score.py 接线公式一致（验收 oracle）。"""
    import math
    if not pf or "A" not in pf or "B" not in pf or not (0 < z < 1):
        return z
    lo = math.log(z / (1.0 - z))
    zc = pf["A"] * lo + pf["B"]
    if zc <= -700:
        return 0.0
    if zc >= 700:
        return 1.0
    return 1.0 / (1.0 + math.exp(-zc))


def demo_posterior(calib):
    """抽样校验：强/中/弱三档的 naive posterior → 再校准值对照表（供接线验收）。纯函数。

    直接用 score.calibrated_probability 算 naive z，再套 §E-2 再校准，输出与接线后
    前端卡片 'prob' 应完全一致。强股样例刻意贴近代码维护抽样（4板/高封单比/早盘/小盘/低换手/有题材）。
    """
    if _scoremod is None:
        return []
    cases = [
        ("强股(4板/封单比8%/09:35早/25亿小盘/换手2%/有题材)", {
            "board_height": 4, "turnover_1": 2.0, "seal_time": "09:35",
            "seal_amount": 8.0 / 100.0 * 25.0 * 10000.0, "float_mv": 25.0, "sectors": ["题材"]}),
        ("中强(2板/封单比3%/10:30/120亿/换手6%/有题材)", {
            "board_height": 2, "turnover_1": 6.0, "seal_time": "10:30",
            "seal_amount": 3.0 / 100.0 * 120.0 * 10000.0, "float_mv": 120.0, "sectors": ["题材"]}),
        ("普通股(1板/封单比1%/13:00/300亿/换手10%/无题材)", {
            "board_height": 1, "turnover_1": 10.0, "seal_time": "13:00",
            "seal_amount": 1.0 / 100.0 * 300.0 * 10000.0, "float_mv": 300.0, "sectors": []}),
        ("弱股(1板/封单比0.4%/14:50尾/800亿大/换手18%/无题材)", {
            "board_height": 1, "turnover_1": 18.0, "seal_time": "14:50",
            "seal_amount": 0.4 / 100.0 * 800.0 * 10000.0, "float_mv": 800.0, "sectors": []}),
    ]
    pf = calib.get("posterior_fit") or {}
    out = []
    for name, feats in cases:
        try:
            res = _scoremod.calibrated_probability(feats, calib, proxy_score=None)
        except Exception:
            continue
        z = res.get("prob")
        if z is None:
            continue
        zc = _recalibrate(z, pf)
        out.append((name, z, zc, res.get("verdict")))
    return out


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
    # Platt scaling 与逐项似然（量化校准增强：见 AGENT_BOARD.md 共识 ②）
    rep["platt_fit"] = fit_platt(rows, rep.get("recommended_weights")) or {}
    rep["per_item_hit_rate"] = per_item_hit_rate(rows)
    # naive 贝叶斯 posterior 再校准（解决 §E 因子同源导致的 posterior 偏高）
    rep["posterior_fit"] = fit_posterior(rows, rep) or {}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    # 抽样校验表（验收 oracle：接线后前端 prob 应与此一致）
    print("\n=== §E-2 抽样校验：naive posterior → 再校准 prob（verdict 按再校准值）===")
    for name, z, zc, _ in demo_posterior(rep):
        import math
        verdict = ("重点" if zc >= 0.50 else "可埋伏" if zc >= 0.35 else "不参与" if zc < 0.10 else "观察")
        print(f"  {name}\n    naive={z:.3f}  →  recalib={zc:.3f}   verdict={verdict}")


if __name__ == "__main__":
    main()
