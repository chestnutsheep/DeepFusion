import json

from deep_fusion.tools.industry import (
    industry_themes,
    industry_themes_dcc,
    industry_themes_causality,
)

print("=" * 60)
print("1. industry_themes — 行业主线识别")
print("=" * 60)
r1 = industry_themes(window=120, n_clusters=5, corr_method="pearson")
d1 = json.loads(r1)
if "error" in d1:
    print("ERROR:", d1["error"])
else:
    print("Meta:", json.dumps(d1["meta"], ensure_ascii=False))
    print()
    for t in d1["themes"]:
        print(f'  主线{t["rank"]}: {t["label"]} | 评分={t["score"]} | 趋势={t["trend"]}')
        print(f'    成员({t["n_members"]}): {", ".join(t["members"])}')
        print(f'    簇内相关={t["avg_intra_corr"]} | 评分明细={t["score_detail"]}')
        print(f'    动量: 5d={t["momentum"]["avg_5d"]}, 10d={t["momentum"]["avg_10d"]}, 20d={t["momentum"]["avg_20d"]}')
        print(f'    资金净额={t["fund_flow"]["net_amount_total"]} | 龙头={t["fund_flow"]["leader_stocks"]}')
        print()
    print("动量TOP10:")
    for m in d1["momentum_ranking"][:10]:
        print(f'  {m["industry"]}: 5d={m["return_5d"]}, 10d={m["return_10d"]}, 20d={m["return_20d"]}')
    print()
    print("PCA主成分:", d1.get("pca_top_contributors", {}))

print()
print("=" * 60)
print("2. industry_themes_dcc — DCC-GARCH 时变条件相关")
print("=" * 60)
r2 = industry_themes_dcc(window=120)
d2 = json.loads(r2)
if "error" in d2:
    print("ERROR:", d2["error"])
else:
    print("Meta:", json.dumps(d2["meta"], ensure_ascii=False))
    print(f'DCC参数: a={d2["dcc_params"]["a"]}, b={d2["dcc_params"]["b"]}, a+b={d2["dcc_params"]["a_plus_b"]}')
    conv = d2["garch_converged"]
    if isinstance(conv, list):
        print(f'GARCH收敛率: {sum(1 for x in conv if x)}/{len(conv)}')
    else:
        print(f'GARCH收敛: {conv}')
    print()
    print("最新期条件相关 TOP10:")
    for p in d2.get("latest_corr_top", [])[:10]:
        print(f'  {p["pair"][0]} ↔ {p["pair"][1]}: corr={p["corr"]}')
    print()
    print("相关变化 TOP10 (联动变化最大的行业对):")
    for p in d2.get("corr_change_top", [])[:10]:
        print(f'  {p["pair"][0]} ↔ {p["pair"][1]}: Δ={p["change"]} ({p["direction"]})')

print()
print("=" * 60)
print("3. industry_themes_causality — Granger因果+龙头行业")
print("=" * 60)
r3 = industry_themes_causality(window=120, max_lag=5)
d3 = json.loads(r3)
if "error" in d3:
    print("ERROR:", d3["error"])
else:
    print("Meta:", json.dumps(d3["meta"], ensure_ascii=False))
    if "note" in d3:
        print("Note:", d3["note"])
    print()
    print("领先行业 (Granger因果龙头):")
    for ind in d3.get("leading_industries", []):
        print(f'  {ind["industry"]}: 领先分={ind["score"]}')
    print()
    print("滞后行业:")
    for ind in d3.get("lagging_industries", []):
        print(f'  {ind["industry"]}: 领先分={ind["score"]}')
    print()
    print("最强因果传导链 TOP10:")
    for p in d3.get("top_causal_pairs", [])[:10]:
        print(f'  {p["source"]} → {p["target"]} (lag={p["lag"]})')
