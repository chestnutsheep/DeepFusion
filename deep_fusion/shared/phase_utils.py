"""四相位通用转化工具

将四周期（基钦/朱格拉/库兹涅茨/康波）不同指标输出映射为
统一的四相位体系 + 带正负信号的数字值，用于宏观综合周期图表。

相位信号约定（cycle_wheel）:
  相位 1 (复苏):   +1.0 — 低于均值但向上，回升
  相位 2 (繁荣):   +2.0 — 高于均值且向上，顶峰
  相位 3 (衰退):   -1.0 — 高于均值但向下，回落
  相位 4 (萧条):   -2.0 — 低于均值且向下，谷底
"""

from __future__ import annotations

from typing import Any

# ── 相位名称字典 ──────────────────────────────────────

MACRO_PHASE_NAMES: dict[int, str] = {
    0: "未知",
    1: "复苏",
    2: "繁荣",
    3: "衰退",
    4: "萧条",
}

KITCHIN_PHASE_NAMES: dict[int, str] = {
    0: "未知",
    1: "主动去库存",
    2: "被动去库存",
    3: "主动补库存",
    4: "被动补库存",
}

KOND_RENAME = {1: "回升期", 2: "繁荣期", 3: "衰退期", 4: "萧条期"}

# ── 阶段-信号值映射 ──────────────────────────────────
# 信号为正：经济扩张方向（复苏+繁荣）
# 信号为负：经济收缩方向（衰退+萧条）
_SIGNAL_MAP: dict[int, float] = {
    1: 1.0,
    2: 2.0,
    3: -1.0,
    4: -2.0,
    0: 0.0,
}

# ── 相位类型 → 名称字典映射 ──────────────────────────
_PHASE_TYPE_MAP = {
    "macro": MACRO_PHASE_NAMES,
    "kitchin": KITCHIN_PHASE_NAMES,
    "kond": KOND_RENAME,
}


def get_phase_name(phase: int, phase_type: str = "macro") -> str:
    """获取相位中文名称

    Args:
        phase: 相位编号 1-4
        phase_type: "macro"(宏观四相), "kitchin"(基钦库存), "kond"(康波长波)

    Returns:
        中文名称，如 "复苏" / "主动去库存"
    """
    names = _PHASE_TYPE_MAP.get(phase_type, MACRO_PHASE_NAMES)
    return names.get(phase, "未知")


def get_phase_signal(phase: int) -> float:
    """获取相位正负信号值（用于综合图表）

    Args:
        phase: 相位编号 1-4 (0=未知)

    Returns:
        信号值: +2(繁荣) / +1(复苏) / -1(衰退) / -2(萧条) / 0(未知)
    """
    return _SIGNAL_MAP.get(phase, 0.0)


def resolve_cycle_phase(
    row: dict[str, Any],
    phase_type: str = "macro",
) -> dict[str, Any]:
    """解析单条周期数据行的相位并添加统一字段

    适配四周期不同输出字段名:
      - 基钦:   row["stage"] + row["stage_name"]   (1-4, "主动去库存")
      - 朱格拉: row["phase"] + row["phase_name"]   (1-4, "复苏")
      - 库兹涅茨: 同上
      - 康波:   row["phase"]                        (1-4 无_name)

    Args:
        row: 周期数据行 dict
        phase_type: 相位类型（决定名称字典）

    Returns:
        添加了统一字段的 dict:
          cycle_phase       — 相位编号 1-4
          cycle_phase_name  — 中文名称
          cycle_signal      — 正负信号值
          cycle_phase_type  — 标记类型
    """
    result = dict(row)

    # 自动检测字段名
    if "stage" in row and row["stage"] is not None:
        phase_val = int(row["stage"])
        name_type = "kitchin"
    elif "phase" in row and row["phase"] is not None:
        phase_val = int(row["phase"])
        name_type = phase_type
    else:
        return result  # 无相位字段，直接返回

    result["cycle_phase"] = phase_val
    result["cycle_phase_name"] = get_phase_name(phase_val, name_type)
    result["cycle_signal"] = get_phase_signal(phase_val)
    result["cycle_phase_type"] = name_type
    return result


def resolve_cycle_series(
    rows: list[dict[str, Any]],
    phase_type: str = "macro",
) -> list[dict[str, Any]]:
    """批量解析周期数据行的相位

    Args:
        rows: 周期数据行列表
        phase_type: 相位类型

    Returns:
        每行都添加了 cycle_phase / cycle_phase_name / cycle_signal
    """
    return [resolve_cycle_phase(r, phase_type) for r in rows]


def build_cycle_signal_value(
    phase: int,
    confidence: float | None = None,
    include_meta: bool = False,
) -> float | dict[str, Any]:
    """构建综合信号值（confidence 加权）

    Args:
        phase: 相位编号 1-4
        confidence: 置信度 0-1（可选）
        include_meta: 是否返回完整元数据

    Returns:
        默认返回 float 信号值;
        include_meta=True 时返回 {signal, phase, name, confidence}
    """
    signal = get_phase_signal(phase)
    if include_meta:
        return {
            "signal": signal,
            "phase": phase,
            "name": get_phase_name(phase),
            "confidence": confidence or 0.0,
        }
    return signal


def normalize_cycle_output(
    cycles_data: dict[str, list[dict[str, Any]] | None],
) -> dict[str, list[dict[str, Any]] | None]:
    """统览四周期数据并归一化相位字段

    Args:
        cycles_data: {"kitchin": [...], "juglar": [...], "kuznets": [...], "kondratiev": [...]}

    Returns:
        同结构，但每行添加了 cycle_phase / cycle_phase_name / cycle_signal
    """
    phase_map: dict[str, str] = {
        "kitchin": "kitchin",
        "juglar": "macro",
        "kuznets": "macro",
        "kondratiev": "kond",
    }
    result = {}
    for cid, rows in cycles_data.items():
        pt = phase_map.get(cid, "macro")
        if rows is None:
            result[cid] = None
        else:
            result[cid] = resolve_cycle_series(rows, pt)
    return result
