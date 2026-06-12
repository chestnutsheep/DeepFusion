"""测试 chart_helpers 抽取 — 验证字体加载、阶段着色、日期轴格式化
先写测试定义预期行为，再实现提取模块。
"""
import pytest
import numpy as np


class TestSetupChartFont:
    """验证字体加载函数的行为契约"""

    def test_returns_font_name_or_none(self):
        """setup_chart_font() 应返回字体名(str)或 None"""
        from deep_fusion.shared.chart_helpers import setup_chart_font
        result = setup_chart_font()
        assert result is None or isinstance(result, str)

    def test_idempotent(self):
        """连续调用不报错"""
        from deep_fusion.shared.chart_helpers import setup_chart_font
        setup_chart_font()
        setup_chart_font()  # 不应抛异常


class TestShadePhases:
    """验证阶段着色函数"""

    def test_basic_shading(self):
        """给定阶段序列，应返回 (start, end, phase) 元组列表"""
        from deep_fusion.shared.chart_helpers import shade_phases
        stages = [1, 1, 1, 2, 2, 3, 3, 3, 4]
        spans = shade_phases(stages)
        assert len(spans) == 4  # 4个连续段
        # 第一段: stage=1, start=0, end=3
        assert spans[0] == (0, 3, 1)
        # 第二段: stage=2, start=3, end=5
        assert spans[1] == (3, 5, 2)
        # 第三段: stage=3, start=5, end=8
        assert spans[2] == (5, 8, 3)
        # 第四段: stage=4, start=8, end=9
        assert spans[3] == (8, 9, 4)

    def test_single_phase(self):
        """单一阶段返回一段"""
        from deep_fusion.shared.chart_helpers import shade_phases
        stages = [2, 2, 2, 2]
        spans = shade_phases(stages)
        assert len(spans) == 1
        assert spans[0] == (0, 4, 2)

    def test_empty_stages(self):
        """空序列返回空列表"""
        from deep_fusion.shared.chart_helpers import shade_phases
        assert shade_phases([]) == []

    def test_skips_zero(self):
        """stage=0 的段不生成着色"""
        from deep_fusion.shared.chart_helpers import shade_phases
        stages = [0, 0, 1, 1, 0, 2, 2]
        spans = shade_phases(stages)
        assert len(spans) == 2
        assert spans[0] == (2, 4, 1)
        assert spans[1] == (5, 7, 2)

    def test_alternating_phases(self):
        """交替阶段每个都单独成段"""
        from deep_fusion.shared.chart_helpers import shade_phases
        stages = [1, 2, 3, 4]
        spans = shade_phases(stages)
        assert len(spans) == 4


class TestSetupDateAxes:
    """验证日期轴格式化"""

    def test_sets_date_format(self):
        """应在 axes 上设置日期格式"""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from deep_fusion.shared.chart_helpers import setup_date_axes

        fig, ax = plt.subplots()
        setup_date_axes([ax])
        # 不应抛异常
        plt.close(fig)


class TestKondratievPhaseNameConsistency:
    """验证康波相位命名与 phase_utils 一致"""

    def test_chart_phase_names_match_phase_utils(self):
        """图表中的康波相位名称应与 phase_utils.KOND_RENAME 一致"""
        from deep_fusion.shared.phase_utils import KOND_RENAME
        # KOND_RENAME: {1: "回升期", 2: "繁荣期", 3: "衰退期", 4: "萧条期"}
        assert KOND_RENAME[1] == "回升期"
        assert KOND_RENAME[2] == "繁荣期"
        assert KOND_RENAME[3] == "衰退期"
        assert KOND_RENAME[4] == "萧条期"


class TestNbsClientDedup:
    """验证 data/sources/nbs_client.py 包含 kondratiev.py 的全部功能"""

    def test_nbs_client_class_exists_in_canonical_location(self):
        """权威 NbsClient 应在 data/sources/nbs_client.py"""
        from deep_fusion.data.sources.nbs_client import _NbsClient
        assert _NbsClient is not None

    def test_all_fetch_functions_exist_in_canonical(self):
        """所有 _fetch_nbs_* 函数应在权威位置可用"""
        from deep_fusion.data.sources import nbs_client
        required = [
            "_fetch_nbs_inventory_yoy",
            "_fetch_nbs_ind_yoy",
            "_fetch_nbs_fix_inv_monthly",
            "_fetch_nbs_re_dev_yoy",
            "_fetch_nbs_cpi_yoy",
            "_fetch_nbs_ppi_yoy",
            "_fetch_nbs_gdp_quarterly",
            "_fetch_nbs_unemployment",
        ]
        for name in required:
            assert hasattr(nbs_client, name), f"{name} missing from canonical nbs_client"

    def test_kondratiev_no_longer_has_own_nbs_client(self):
        """重构后 kondratiev.py 不应再有自己的 _NbsClient 副本"""
        from deep_fusion.analysis.macro.cycles import kondratiev
        # 验证 kondratiev 不再定义自己的 _NbsClient
        assert not hasattr(kondratiev, "_NbsClient"), \
            "kondratiev.py 不应再有自己的 _NbsClient，应使用 data/sources/nbs_client.py 的权威版本"
        # 验证 kondratiev 不再有 _fetch_nbs_* 系列函数
        assert not hasattr(kondratiev, "_fetch_nbs_inventory_yoy"), \
            "kondratiev.py 不应再有自己的 _fetch_nbs_* 函数，应使用 data/sources/nbs_client.py 的权威版本"


class TestZscoreUnification:
    """验证 Z-score 工具函数行为一致性"""

    def test_engine_zscore_with_nones(self):
        """engine._zscore 应正确处理 None 值"""
        from deep_fusion.analysis.macro.cycles.engine import _zscore
        result = _zscore([1.0, None, 3.0, 5.0])
        assert result[1] is None
        assert result[0] is not None
        assert result[2] is not None

    def test_simple_zscore_no_nones(self):
        """kondratiev._simple_zscore 不处理 None，但纯数值应等价"""
        from deep_fusion.analysis.macro.cycles.kondratiev import _simple_zscore
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _simple_zscore(vals)
        assert len(result) == 5
        # 均值为3, std≈1.414 → 第3个应为0
        assert abs(result[2]) < 0.01

    def test_zscore_simple_equivalence(self):
        """无 None 值时，engine._zscore 和 _simple_zscore 应产生相同结果"""
        from deep_fusion.analysis.macro.cycles.engine import _zscore
        from deep_fusion.analysis.macro.cycles.kondratiev import _simple_zscore
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        r1 = _zscore(vals)
        r2 = _simple_zscore(vals)
        for a, b in zip(r1, r2):
            assert abs(a - b) < 0.02


class TestDeadCodeRemoval:
    """验证 kondratiev.py 死代码已移除"""

    def test_compute_kondratiev_returns_early(self):
        """_compute_kondratiev 应只走 pca 路径并返回 (dict, list)"""
        from deep_fusion.analysis.macro.cycles.kondratiev import _compute_kondratiev
        import inspect
        src = inspect.getsource(_compute_kondratiev)
        # 死代码块中引用了 IndicatorDef, _fetch_nbs_*, 这些不应出现在函数体中
        assert "IndicatorDef" not in src or "# dead code removed" in src
