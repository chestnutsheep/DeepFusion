"""kitchin cycle classification"""
from .engine import _institutional_preprocess, _direction, _ma

def _classify_kitchin(periods: list[str], data: dict, cfg: CycleConfig) -> list[dict]:
    dem = [data[p].get("demand_yoy") for p in periods]
    inv = [data[p].get("inventory_yoy") for p in periods]
    dem_s = _ma(dem, cfg.ma_window)
    inv_s = _ma(inv, cfg.ma_window)
    dem_z = _institutional_preprocess(dem, low_yr=3, high_yr=5, fs=12)
    inv_z = _institutional_preprocess(inv, low_yr=3, high_yr=5, fs=12)
    stage_names = {1: "主动去库存", 2: "被动去库存", 3: "主动补库存", 4: "被动补库存"}
    results = []
    for i, p in enumerate(periods):
        dd = _direction(dem_z[i], dem_z[i - 1] if i > 0 else None)
        idir = _direction(inv_z[i], inv_z[i - 1] if i > 0 else None)
        stage = 0
        if dd is not None and idir is not None:
            if dd == -1 and idir == -1: stage = 1
            elif dd == 1 and idir == -1: stage = 2
            elif dd == 1 and idir == 1: stage = 3
            elif dd == -1 and idir == 1: stage = 4
        real_inv = (data[p].get("inventory_yoy") or 0) - ((data[p].get("pmi") or 50) - 50)
        results.append({
            "period": p, "demand_yoy": data[p].get("demand_yoy"),
            "inventory_yoy": data[p].get("inventory_yoy"),
            "demand_z": dem_z[i], "inventory_z": inv_z[i],
            "pmi": data[p].get("pmi"), "m2_yoy": data[p].get("m2_yoy"),
            "fix_inv_yoy": data[p].get("fix_inv_yoy"),
            "real_inventory_yoy": real_inv,
            "stage": stage, "stage_name": stage_names.get(stage, "未知"),
            "demand_dir": dd, "inventory_dir": idir,
        })
    return results


"""juglar cycle classification"""
from .engine import _institutional_preprocess, _direction, _ma

def _classify_juglar(periods: list[str], data: dict, cfg: CycleConfig) -> list[dict]:
    # 四指标加权: 设备投资(0.4) + 制造业固投(0.25) + 固投总量(0.15) + 产能利用率(0.2)
    eq_v = [data[p].get("equip_yoy") for p in periods]
    mf_v = [data[p].get("manufacturing_yoy") for p in periods]
    fx_v = [data[p].get("fix_inv_yoy") for p in periods]
    cu_v = [data[p].get("capacity_util") for p in periods]
    eq_z = _institutional_preprocess(eq_v, low_yr=6, high_yr=12, fs=12)
    mf_z = _institutional_preprocess(mf_v, low_yr=6, high_yr=12, fs=12)
    fx_z = _institutional_preprocess(fx_v, low_yr=6, high_yr=12, fs=12)
    cu_z = _institutional_preprocess(cu_v, low_yr=6, high_yr=12, fs=12)
    # 加权合成
    comp_z: list[float | None] = []
    for i in range(len(periods)):
        avail = [(v, w) for v, w in [(eq_z[i], 0.4), (mf_z[i], 0.25), (fx_z[i], 0.15), (cu_z[i], 0.2)] if v is not None]
        if avail:
            total_w = sum(w for _, w in avail)
            comp_z.append(round(sum(v * w for v, w in avail) / total_w, 4))
        else:
            comp_z.append(None)
    phase_names = {1: "复苏", 2: "繁荣", 3: "衰退", 4: "萧条"}
    results = []
    for i, p in enumerate(periods):
        z, g = comp_z[i], _direction(comp_z[i], comp_z[i - 1] if i > 0 else None)
        phase = 0
        if comp_z[i] is not None and g is not None:
            if z > 0 and g >= 0:     phase = 2
            elif z <= 0 and g >= 0:  phase = 1
            elif z > 0 and g < 0:    phase = 3
            elif z <= 0 and g < 0:   phase = 4
        results.append({
            "period": p,
            "equip_yoy": eq_v[i], "manufacturing_yoy": mf_v[i], "fix_inv_yoy": fx_v[i],
            "capacity_util": cu_v[i], "comp_z": comp_z[i],
            "pmi": data[p].get("pmi"), "ppi_yoy": data[p].get("ppi_yoy"),
            "ind_yoy": data[p].get("ind_yoy"),
            "phase": phase, "phase_name": phase_names.get(phase, "未知"),
            "fix_dir": g,
        })
    return results


"""kuznets cycle classification"""
from .engine import _institutional_preprocess, _direction, _ma

def _classify_kuznets(periods: list[str], data: dict, cfg: CycleConfig) -> list[dict]:
    # 四指标加权: 房价(0.5) + 销售面积(0.2) + 新开工面积(0.2) + 开发投资(0.1)
    hp_v = [data[p].get("house_price_yoy") for p in periods]
    sa_v = [data[p].get("sales_yoy") for p in periods]
    ns_v = [data[p].get("new_start_yoy") for p in periods]
    re_v = [data[p].get("re_yoy") for p in periods]
    hp_z = _institutional_preprocess(hp_v, low_yr=12, high_yr=30, fs=12)
    sa_z = _institutional_preprocess(sa_v, low_yr=12, high_yr=30, fs=12)
    ns_z = _institutional_preprocess(ns_v, low_yr=12, high_yr=30, fs=12)
    re_z = _institutional_preprocess(re_v, low_yr=12, high_yr=30, fs=12)
    # 加权合成: 房价为主
    comp_z: list[float | None] = []
    for i in range(len(periods)):
        hp, sa, ns, re = hp_z[i], sa_z[i], ns_z[i], re_z[i]
        avail = [(v, w) for v, w in [(hp, 0.5), (sa, 0.2), (ns, 0.2), (re, 0.1)] if v is not None]
        if avail:
            total_w = sum(w for _, w in avail)
            comp_z.append(round(sum(v * w for v, w in avail) / total_w, 4))
        else:
            comp_z.append(None)
    phase_names = {1: "复苏", 2: "繁荣", 3: "衰退", 4: "萧条"}
    results = []
    for i, p in enumerate(periods):
        z, g = comp_z[i], _direction(comp_z[i], comp_z[i - 1] if i > 0 else None)
        phase = 0
        if comp_z[i] is not None and g is not None:
            if z > 0 and g >= 0:     phase = 2
            elif z <= 0 and g >= 0:  phase = 1
            elif z > 0 and g < 0:    phase = 3
            elif z <= 0 and g < 0:   phase = 4
        results.append({
            "period": p,
            "house_price_yoy": hp_v[i],
            "sales_yoy": sa_v[i], "new_start_yoy": ns_v[i], "re_yoy": re_v[i],
            "comp_z": comp_z[i],
            "pmi": data[p].get("pmi"),
            "phase": phase, "phase_name": phase_names.get(phase, "未知"),
            "re_dir": g,
        })
    return results


# ── 4 份配置表 ──────────────────────────────────────────

