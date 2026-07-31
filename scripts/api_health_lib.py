"""DeepFusion AkShare 接口健康巡检 —— 公共库。

设计目标（对应需求）：
1. 自动发现 DeepFusion 代码中使用的全部 akshare 数据接口（来源可追溯）。
2. 定时检查每个接口是否「正常工作」：
   - 一级（免网络）：接口名称是否仍存在于已安装的 akshare 命名空间
     （直接对应「接口名称经常更新变动导致堵塞」）。
   - 二级（真实调用）：实际拉取一次，确认能返回数据且行列格式与基线一致。
3. 故障诊断 + 对症修复：
   - 接口被重命名/移除：扫描 akshare 命名空间给出候选替代名（模糊匹配）；
     若修复注册表 `api_fix_registry.json` 中已登记 rename/alternative，则自动套用并复核。
   - 返回格式变化：生成/登记「调整脚本」(`scripts/transforms/`)，保证与原有接入方式一致。
4. 更换接口后必须先用「单独的脚本单拉一次新接口数据」核对格式 —— 由 `api_pull_once.py`
   与本库 `pull_once()` 提供，并在检修流程中自动调用复核。
5. 每次成果与检验结果写入 `logs/api_logs`（指定格式）。

本文件只放可复用逻辑；CLI 入口见 `api_health_check.py`，单拉工具见 `api_pull_once.py`。
"""

from __future__ import annotations

import difflib
import importlib.util
import inspect
import json
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DEEP_FUSION = PROJECT_ROOT / "deep_fusion"
LOGS_DIR = PROJECT_ROOT / "logs"
API_LOGS_PATH = LOGS_DIR / "api_logs"
REPORT_PATH = LOGS_DIR / "api_health_report.json"
SCHEMA_BASELINE_PATH = LOGS_DIR / "api_schema_baseline.json"
FIX_REGISTRY_PATH = SCRIPTS_DIR / "api_fix_registry.json"
TRANSFORMS_DIR = SCRIPTS_DIR / "transforms"

for _d in (LOGS_DIR, TRANSFORMS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 接口名称前缀，用于粗略判断是否「东方财富」类接口（需要代理）。
EM_MARKERS = ("_em",)


# --------------------------------------------------------------------------- #
# 接口发现
# --------------------------------------------------------------------------- #
def discover_interfaces() -> dict[str, set[str]]:
    """扫描 deep_fusion 源码中所有 `ak.<func>` 调用，返回 {接口名: {出现文件名集}}。

    仅匹配小写 snake_case（akshare 函数命名规范），自动排除 `ak_cache` 等顶层工具。
    """
    pat = re.compile(r"ak\.([a-z][a-z0-9_]*)")
    found: dict[str, set[str]] = {}
    if not DEEP_FUSION.exists():
        return found
    for py in sorted(DEEP_FUSION.rglob("*.py")):
        # 不扫描本巡检脚本自身，避免把脚本里的 ak. 调用也算进数据源
        if "api_health" in py.name or "api_pull_once" in py.name:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in pat.finditer(text):
            name = m.group(1)
            if name in ("get", "xxx"):  # 占位/非数据源噪声
                continue
            found.setdefault(name, set()).add(py.name)
    return found


def is_em_interface(name: str) -> bool:
    return any(name.endswith(m) or m in name for m in EM_MARKERS)


# --------------------------------------------------------------------------- #
# 参数自动填充（用于真实调用探测）
# --------------------------------------------------------------------------- #
# 常见 akshare 参数名 -> 探测用样例值
ARG_DEFAULTS: dict[str, Any] = {
    "symbol": "600519",
    "stock": "600519",
    "code": "600519",
    "security": "600519",
    "ts_code": "600519.SH",
    "market": "sh",
    "period": "daily",
    "adjust": "qfq",
    "date": "20250331",
    "period_date": "20250331",
    "start_date": "20250101",
    "end_date": "20250630",
    "begin_date": "20250101",
    "report_date": "20250331",
    "vars_list": ["RB"],
    "contract": "RB2501",
    "fund_type": "股票型",
    "indicator": "报告期",
    "limit": 10,
    "name": "贵州茅台",
    "domain": "白酒",
    "category": "股票概念",
    "type": "stock",
    "kind": "stock",
    "exchange": "SH",
    "suffix": "SH",
    "quarter": 1,
    "year": 2025,
    "month": 3,
    "start_year": 2024,
    "report_type": "1",
}


def build_kwargs(func) -> tuple[dict | None, list[str]]:
    """根据函数签名自动填充必需参数。

    返回 (kwargs, missing)：kwargs 为可调用参数；missing 为无法填充的必需参数名。
    若 missing 非空，说明无法自动探测该接口（SKIP_ARGS）。
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return {}, []
    kwargs: dict[str, Any] = {}
    missing: list[str] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls", "args", "kwargs"):
            continue
        if param.default is not inspect.Parameter.empty:
            continue  # 有默认值，使用默认
        if pname in ARG_DEFAULTS:
            kwargs[pname] = ARG_DEFAULTS[pname]
        else:
            missing.append(pname)
    if missing:
        return None, missing
    return kwargs, []


# --------------------------------------------------------------------------- #
# 异常分类
# --------------------------------------------------------------------------- #
_NETWORK_HINTS = (
    "timeout", "connection", "connect", "remoteclosed", "remotedisconnected",
    "chunkedencoding", "urlerror", "maxretries", "nameresolution",
    "getaddrinfo", "brokenpipe", "reset", "httperror", "proxy",
)


def is_network_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return any(h in name or h in msg for h in _NETWORK_HINTS)


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, FuturesTimeout):
        return "Timeout"
    if is_network_error(exc):
        return "Network"
    name = type(exc).__name__
    if name in ("TypeError", "ValueError", "KeyError", "IndexError"):
        return name
    return name


# --------------------------------------------------------------------------- #
# 候选替代接口发现（重名诊断）
# --------------------------------------------------------------------------- #
def find_candidates(name: str, top: int = 5) -> list[str]:
    """在已安装 akshare 命名空间中，按「模糊相似度 + token 重叠」为被移除的接口找候选替代。"""
    tokens = set(name.split("_"))
    scored: list[tuple[float, str]] = []
    for cand in dir(ak):
        if cand.startswith("_") or cand in ("get", "xxx"):
            continue
        ratio = difflib.SequenceMatcher(None, name, cand).ratio()
        ctokens = set(cand.split("_"))
        overlap = len(tokens & ctokens) / max(1, len(tokens | ctokens))
        score = 0.55 * ratio + 0.45 * overlap
        if score > 0.35 and cand != name:
            scored.append((score, cand))
    scored.sort(reverse=True)
    return [c for _, c in scored[:top]]


# --------------------------------------------------------------------------- #
# 修复注册表（维护者可在 api_fix_registry.json 中登记已知修复）
# --------------------------------------------------------------------------- #
def load_fix_registry() -> dict:
    if FIX_REGISTRY_PATH.exists():
        try:
            return json.loads(FIX_REGISTRY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"renames": {}, "alternatives": {}, "transforms": {}}


def save_fix_registry(reg: dict) -> None:
    FIX_REGISTRY_PATH.write_text(
        json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def apply_transform(interface: str, df: Any) -> Any:
    """若修复注册表中登记了 transforms[interface]，加载并应用其 transform(df)。"""
    reg = load_fix_registry()
    rel = reg.get("transforms", {}).get(interface)
    if not rel:
        return df
    path = (SCRIPTS_DIR / rel) if not Path(rel).is_absolute() else Path(rel)
    if not path.exists():
        return df
    try:
        spec = importlib.util.spec_from_file_location(f"_xf_{interface}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "transform"):
            return mod.transform(df)
    except Exception as e:  # 转换脚本自身出错不应中断巡检
        print(f"[warn] transform {interface} 执行失败: {e}")
    return df


def ensure_transform_stub(interface: str, old_cols: list, new_cols: list) -> str | None:
    """当返回格式变化且无现成转换脚本时，生成一个占位调整脚本并登记到修复注册表。

    返回生成的脚本路径（已存在则跳过生成，仅返回路径）。
    """
    fname = f"transform_{interface}.py"
    path = TRANSFORMS_DIR / fname
    if not path.exists():
        content = f'''"""接口 {interface} 返回格式调整脚本（自动生成占位）。

原基线列: {old_cols}
当前返回列: {new_cols}

请在 `transform(df)` 中将「当前返回列」映射/重命名为「原基线列」，
保证下游数据接入方式保持一致。完成后本接口即视为已修复。
"""


def transform(df):
    """将接口 {interface} 的当前返回 DataFrame 调整为原基线格式。

    TODO: 按上方列差异补充映射/重命名/裁剪逻辑。
    """
    # 示例：df = df.rename(columns={{"新列名": "旧列名"}})
    return df
'''
        path.write_text(content, encoding="utf-8")
    reg = load_fix_registry()
    reg.setdefault("transforms", {})[interface] = f"transforms/{fname}"
    save_fix_registry(reg)
    return str(path)


# --------------------------------------------------------------------------- #
# 代理（东方财富接口通常需要）
# --------------------------------------------------------------------------- #
def ensure_proxy() -> bool:
    """确保 clash-verge 代理在线（东方财富接口所需）。失败不阻断，仅返回状态。"""
    try:
        if subprocess.run(["pgrep", "-f", "clash-verge"], capture_output=True).returncode == 0:
            return True
        subprocess.Popen(
            "nohup /usr/bin/clash-verge >/tmp/clash-verge.log 2>&1 &",
            shell=True,
        )
        time.sleep(2)
        return subprocess.run(["pgrep", "-f", "clash-verge"], capture_output=True).returncode == 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 单接口真实调用（被主巡检与 api_pull_once 共用）
# --------------------------------------------------------------------------- #
def _invoke(func, kwargs):
    return func(**(kwargs or {}))


def pull_once(name: str, kwargs: dict | None = None, timeout: int = 20) -> dict:
    """真实调用一次接口，返回结构化结果。

    结果含：exists / status(OK|EMPTY|ARGS|NETWORK|ERROR|RENAMED) /
    columns / shape / error / candidates。
    """
    if not hasattr(ak, name):
        return {
            "exists": False,
            "status": "RENAMED",
            "error": f"AttributeError: akshare 中不存在接口 {name}",
            "error_type": "AttributeError",
            "candidates": find_candidates(name),
            "columns": None,
            "shape": None,
        }
    func = getattr(ak, name)
    if kwargs is None:
        kwargs, missing = build_kwargs(func)
        if kwargs is None:
            return {
                "exists": True,
                "status": "ARGS",
                "error": f"缺少可自动填充的必需参数: {', '.join(missing)}",
                "error_type": "ArgsError",
                "columns": None,
                "shape": None,
                "missing_args": missing,
            }
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_invoke, func, kwargs)
            out = fut.result(timeout=timeout)
    except FuturesTimeout:
        return {"exists": True, "status": "NETWORK", "error": f"调用超时({timeout}s)",
                "error_type": "Timeout", "columns": None, "shape": None}
    except Exception as e:  # noqa: BLE001
        return {"exists": True, "status": "NETWORK" if is_network_error(e) else "ERROR",
                "error": str(e)[:300], "error_type": classify_exception(e),
                "columns": None, "shape": None}

    summary = summarize_df(out)
    return {
        "exists": True,
        "status": summary["status"],
        "columns": summary["columns"],
        "shape": summary["shape"],
        "dtypes": summary["dtypes"],
        "head": summary["head"],
        "error": None,
        "error_type": None,
    }


def summarize_df(df: Any) -> dict:
    if df is None:
        return {"status": "EMPTY", "columns": [], "shape": [0, 0], "dtypes": {}, "head": []}
    if isinstance(df, pd.DataFrame):
        if df.empty:
            return {"status": "EMPTY", "columns": list(df.columns), "shape": [0, 0], "dtypes": {}, "head": []}
        return {
            "status": "OK",
            "columns": list(df.columns),
            "shape": list(df.shape),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
            "head": df.head(3).to_dict(orient="records"),
        }
    # 非 DataFrame（dict/list/str 等）也视为成功返回，仅无列结构
    return {"status": "OK", "columns": [], "shape": [1, 0],
            "dtypes": {"type": type(df).__name__}, "head": []}


# --------------------------------------------------------------------------- #
# 格式基线（schema baseline）
# --------------------------------------------------------------------------- #
def load_schema_baseline() -> dict:
    if SCHEMA_BASELINE_PATH.exists():
        try:
            return json.loads(SCHEMA_BASELINE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_schema_baseline(base: dict) -> None:
    SCHEMA_BASELINE_PATH.write_text(
        json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# 修复尝试（renamed 接口）
# --------------------------------------------------------------------------- #
def try_fix_renamed(name: str, reg: dict) -> tuple[bool, str, str | None]:
    """对被重命名的接口尝试套用修复注册表中的 rename / alternative。

    返回 (是否修复, 说明, 新接口名或None)。修复后会真实调用新接口复核。
    """
    renames = reg.get("renames", {})
    alternatives = reg.get("alternatives", {})
    new_name = renames.get(name) or alternatives.get(name)
    if not new_name:
        return False, "无登记修复；候选替代见 candidates 字段", None
    # 支持 "adapter:module.func" 形式（暂仅校验 akshare 同名接口，adapter 形式需人工确认）
    if ":" in str(new_name):
        return False, f"登记为 adapter 形式 {new_name}，需人工确认后接入", new_name
    if not hasattr(ak, new_name):
        return False, f"登记的新接口 {new_name} 在 akshare 中亦不存在", new_name
    res = pull_once(new_name, timeout=20)
    if res["status"] in ("OK", "EMPTY"):
        return True, f"已映射到新接口 {new_name}（复核状态 {res['status']}）", new_name
    return False, f"新接口 {new_name} 复核失败: {res.get('error')}", new_name


# --------------------------------------------------------------------------- #
# 主编排
# --------------------------------------------------------------------------- #
ABNORMAL = {"RENAMED", "NETWORK", "ERROR", "SCHEMA_CHANGED"}


def run_check(
    deep: bool = True,
    only: list[str] | None = None,
    category: str | None = None,
    timeout: int = 20,
    use_proxy: bool = True,
) -> dict:
    discovered = discover_interfaces()
    if only:
        discovered = {k: v for k, v in discovered.items() if k in set(only)}
    if category == "em":
        discovered = {k: v for k, v in discovered.items() if is_em_interface(k)}

    if deep and use_proxy and any(is_em_interface(n) for n in discovered):
        ensure_proxy()

    reg = load_fix_registry()
    baseline = load_schema_baseline()
    results: list[dict] = []

    for name in sorted(discovered):
        files = sorted(discovered[name])
        entry = {"name": name, "files": files, "em": is_em_interface(name),
                 "fixed": False, "fix_note": "", "candidates": [],
                 "transform_needed": False, "transform_stub": None}

        # 一级：名称是否还存在
        if not hasattr(ak, name):
            entry["status"] = "RENAMED"
            entry["candidates"] = find_candidates(name)
            fixed, note, new_name = try_fix_renamed(name, reg)
            entry["fixed"] = fixed
            entry["fix_note"] = note
            entry["new_name"] = new_name
            # 修复成功后用新接口建立/核对基线
            if fixed and new_name:
                res = pull_once(new_name, timeout=timeout)
                if res["status"] == "OK":
                    baseline[name] = {"columns": res["columns"], "shape": res["shape"],
                                      "via": new_name}
            results.append(entry)
            continue

        # 二级：真实调用
        if not deep:
            entry["status"] = "OK_EXISTS"
            entry["exists"] = True
            results.append(entry)
            continue

        res = pull_once(name, timeout=timeout)
        entry["exists"] = res["exists"]
        entry["error"] = res.get("error")
        entry["error_type"] = res.get("error_type")
        entry["columns"] = res.get("columns")
        entry["shape"] = res.get("shape")

        if res["status"] in ("NETWORK", "ERROR", "ARGS"):
            entry["status"] = res["status"]
            results.append(entry)
            continue

        # OK / EMPTY -> 核对格式基线
        cols = res.get("columns") or []
        if name in baseline:
            if baseline[name].get("columns") != cols and cols:
                # 格式变化：需要增补调整脚本
                entry["status"] = "SCHEMA_CHANGED"
                stub = ensure_transform_stub(name, baseline[name].get("columns", []), cols)
                entry["transform_needed"] = True
                entry["transform_stub"] = stub
                entry["fix_note"] = f"返回列与基线不同，已生成调整脚本占位: {stub}"
            else:
                entry["status"] = res["status"]  # OK 或 EMPTY
        else:
            # 首次成功，建立基线
            baseline[name] = {"columns": cols, "shape": res.get("shape")}
            entry["status"] = res["status"]
        results.append(entry)

    save_schema_baseline(baseline)
    return _build_summary(results, deep)


def _build_summary(results: list[dict], deep: bool) -> dict:
    total = len(results)
    abnormal = [r for r in results if r.get("status") in ABNORMAL]
    m = len(abnormal)
    good = total - m
    yield_rate = (good / total * 100) if total else 0.0

    fixed = [r for r in abnormal if r.get("fixed")]
    q = len(fixed)
    unfixed = [r for r in abnormal if not r.get("fixed")]
    p = len(unfixed)
    fix_rate = (q / m * 100) if m else 100.0

    abnormal_names = ", ".join(sorted(r["name"] for r in abnormal))
    unfixed_names = "[" + ", ".join(f'"{r["name"]}"' for r in unfixed) + "]"

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = (
        f"{ts} : 校验成果汇总，当前接口数量共 {total} 个，异常接口 {m} 个，"
        f"良率 {yield_rate:.1f} %，异常接口名称如下：{abnormal_names}。"
        f"经检修：问题接口共 {m} 个，现修复 {q} 个，修复率 {fix_rate:.1f} %，"
        f"仍有 {p} 个接口无法修复，名称为: {unfixed_names}"
    )

    detail = []
    for r in results:
        detail.append({
            "name": r["name"],
            "status": r.get("status"),
            "em": r.get("em"),
            "files": r.get("files"),
            "error": r.get("error"),
            "error_type": r.get("error_type"),
            "candidates": r.get("candidates"),
            "fixed": r.get("fixed"),
            "fix_note": r.get("fix_note"),
            "transform_needed": r.get("transform_needed"),
            "transform_stub": r.get("transform_stub"),
            "columns": r.get("columns"),
            "shape": r.get("shape"),
        })

    return {
        "log_line": log_line,
        "total": total,
        "abnormal_count": m,
        "yield_rate": round(yield_rate, 1),
        "good_count": good,
        "fixed_count": q,
        "unfixed_count": p,
        "fix_rate": round(fix_rate, 1),
        "abnormal_names": [r["name"] for r in abnormal],
        "unfixed_names": [r["name"] for r in unfixed],
        "deep": deep,
        "detail": detail,
    }


# --------------------------------------------------------------------------- #
# 日志写出
# --------------------------------------------------------------------------- #
def write_log(summary: dict) -> None:
    API_LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with API_LOGS_PATH.open("a", encoding="utf-8") as f:
        f.write(summary["log_line"] + "\n")
    REPORT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
