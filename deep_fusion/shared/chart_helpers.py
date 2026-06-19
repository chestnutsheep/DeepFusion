"""图表绘制公共工具 — 字体加载、阶段着色、日期轴格式化

从 kondratiev.py 四个图表函数中提取的重复代码。
前端不改动，这些工具仅被后端图表函数使用。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 字体路径候选列表 ──────────────────────────────────────

_FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def setup_chart_font() -> str | None:
    """加载中文字体，返回字体名或 None

    从 kondratiev.py 四个 _gen_*_chart 函数中提取的重复字体加载逻辑。
    设置 matplotlib 全局字体，确保中文标签正常显示。
    """
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    for _p in _FONT_PATHS:
        if Path(_p).exists():
            _fp = fm.FontProperties(fname=_p)
            plt.rcParams["font.family"] = _fp.get_name()
            return _fp.get_name()
    return None


def shade_phases(stages: list[int]) -> list[tuple[int, int, int]]:
    """检测连续相同阶段 → 返回着色区间列表

    从四个 _gen_*_chart 函数中提取的重复"检测连续相同阶段→axvspan着色"逻辑。

    Args:
        stages: 阶段编号列表，如 [1, 1, 1, 2, 2, 3, 3, 3, 4]

    Returns:
        [(start_idx, end_idx, phase), ...] 元组列表
        其中 stage=0 的段被跳过（不着色）
    """
    if not stages:
        return []

    current_stage: int | None = None
    stage_start = 0
    spans: list[tuple[int, int, int]] = []

    for i, s in enumerate(stages + [0]):
        if s != current_stage:
            if current_stage is not None and current_stage != 0:
                spans.append((stage_start, i, current_stage))
            current_stage = s
            stage_start = i
        if i == len(stages):
            break

    return spans


def apply_phase_shading(
        ax,
        dates: list,
        stages: list[int],
        colors: dict[int, str],
        alpha: float = 0.12,
) -> None:
    """在 matplotlib axes 上应用阶段着色

    Args:
        ax: matplotlib Axes 对象
        dates: 日期列表（用于 axvspan 边界）
        stages: 阶段编号列表
        colors: {phase: color_str} 映射
        alpha: 着色透明度
    """
    spans = shade_phases(stages)
    for ss, se, s in spans:
        end_idx = min(se, len(dates) - 1)
        ax.axvspan(dates[ss], dates[end_idx], alpha=alpha, color=colors.get(s, "#ccc"))


def setup_date_axes(axes: list, year_interval: int = 2) -> None:
    """设置日期轴格式

    从四个 _gen_*_chart 函数中提取的重复日期格式化逻辑。

    Args:
        axes: matplotlib Axes 列表
        year_interval: 年份标签间隔
    """
    import matplotlib.dates as mdates

    for ax in axes:
        ax.xaxis.set_major_locator(mdates.YearLocator(year_interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", rotation=45, labelsize=8)


def setup_matplotlib_agg() -> None:
    """设置 matplotlib 为非交互式 Agg 后端（图表生成必须）

    从 kondratiev.py 顶部和四个函数内部提取的重复设置。
    只需在模块加载时调用一次。
    """
    import matplotlib
    matplotlib.use("Agg")
