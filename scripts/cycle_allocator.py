"""

Deep Fusion 四周期嵌套资产配置引擎 - CLI 入口（已重构）

================================================================================
历史：本脚本早期版本使用离散相位查表 ``PHASE_WEIGHTS``（复苏/繁荣/衰退/萧条
四档 + 固定权重），属于经验拍脑袋方案，已被 consensus 框架取代。

现作为 ``deep_fusion.tools.allocation`` 的薄 CLI 包装，复用同一套
「风险平价战略基准 + 四周期 composite_z regime 战术倾斜」共识逻辑。
所有真实计算见 ``deep_fusion/tools/allocation.py``，本文件仅提供命令行/
脚本调用入口，避免重复实现。
================================================================================
"""

import json
import sys

from deep_fusion.tools.allocation import asset_allocation, _compute_allocation


def _print_result():
    out = asset_allocation()
    print(out)


def main():
    """命令行入口。

    用法:
      python cycle_allocator.py            # 打印最新资产配置 JSON
      python cycle_allocator.py json       # 同上（显式）
      python cycle_allocator.py report     # 打印 Markdown 简报
    """
    cmd = sys.argv[1] if len(sys.argv) > 1 else "json"

    if cmd in ("json", "alloc", ""):
        _print_result()
        return

    if cmd == "report":
        r = _compute_allocation()
        wp = r["weights_pct"]
        reg = r["regime"]
        lines = [
            "# Deep Fusion 资产配置简报",
            "",
            f"- 生成时间: {r['updated_at']}",
            f"- 数据基准: {r['data_date']}",
            f"- 周期 regime: {reg['label']} (tilt={reg['tilt']})",
            f"- 方法: {r['methodology']['strategic']}；{r['methodology']['tactical']}",
            "",
            "## 大类资产配置",
            "",
            f"- 股票: **{wp.get('股票')}%**",
            f"- 债券: **{wp.get('债券')}%**",
            f"- 商品: **{wp.get('商品')}%**",
            f"- 现金: **{wp.get('现金')}%**",
            "",
            "## 四周期输入",
            "",
        ]
        for c in r["cycles"]:
            lines.append(f"- {c['cycle']}: z={c['z']} 相位={c['phase_name']}")
        lines.append("")
        lines.append("*由 Deep Fusion 四周期资产配置引擎自动生成，仅供参考，不构成投资建议。*")
        print("\n".join(lines))
        return

    print(f"未知命令: {cmd}（可用: json / report）")
    sys.exit(1)


if __name__ == "__main__":
    main()
