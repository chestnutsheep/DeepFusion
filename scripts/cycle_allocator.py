"""

Deep Fusion 四周期嵌套资产配置引擎 - 核心计算脚本

Four-Cycle Nested Asset Allocation Engine


基于基钦/朱格拉/库兹涅茨/康波四周期加权共振算法，

自动计算大类资产配置比例、行业配置建议和调仓提醒。

"""


import json

import sys

from datetime import datetime

from typing import Dict, List, Optional, Tuple


# ============================================================

# 1. 基准权重表

# ============================================================


PHASE_WEIGHTS = {

    # 复苏（被动去库存）：股票>商品>债券>现金

    "复苏": {"stock": 0.60, "bond": 0.20, "commodity": 0.15, "cash": 0.05},

    # 繁荣（主动补库存）：商品>股票>债券>现金

    "繁荣": {"stock": 0.40, "bond": 0.10, "commodity": 0.45, "cash": 0.05},

    # 衰退（被动补库存）：债券>现金>股票>商品

    "衰退": {"stock": 0.15, "bond": 0.60, "commodity": 0.05, "cash": 0.20},

    # 萧条（主动去库存）：现金>债券>商品>股票

    "萧条": {"stock": 0.05, "bond": 0.35, "commodity": 0.10, "cash": 0.50}

}


CYCLE_CONFIG = {

    "kitchin":   {"name": "基钦周期", "name_en": "Kitchin",  "span": "6-12个月", "weight": 0.4, "role": "决定短期战术仓位"},

    "juglar":    {"name": "朱格拉周期", "name_en": "Juglar",  "span": "3-5年",    "weight": 0.3, "role": "决定中期战略方向"},

    "kuznets":   {"name": "库兹涅茨周期", "name_en": "Kuznets", "span": "7-10年",  "weight": 0.2, "role": "决定大类资产长期偏好"},

    "kontratieff":{"name": "康波周期", "name_en": "Kontratieff","span": "50-60年", "weight": 0.1, "role": "决定超长期资产底色"}

}


RISK_PREFERENCE_ADJUSTMENT = {

    "保守": {"stock": -10, "bond": 5, "commodity": -5, "cash": 10},

    "稳健": {"stock": 0, "bond": 0, "commodity": 0, "cash": 0},

    "激进": {"stock": 10, "bond": -5, "commodity": 5, "cash": -10}

}


ASSET_NAMES = {

    "stock": "股票",

    "bond": "债券",

    "commodity": "商品",

    "cash": "现金"

}


PHASE_VALUES = {"复苏": 25, "繁荣": 75, "衰退": 125, "萧条": 175}



# ============================================================

# 2. 核心计算函数

# ============================================================


def calculate_portfolio(kitchin_phase: str, juglar_phase: str,

                        kuznets_phase: str, kontratieff_phase: str) -> Dict[str, int]:

    """

    四周期加权共振法：计算最终资产配置比例。


    输入：四个周期的相位（"复苏"/"繁荣"/"衰退"/"萧条"）

    输出：最终的资产配置比例字典（百分比整数）

    """

    phases = [kitchin_phase, juglar_phase, kuznets_phase, kontratieff_phase]


    # 校验相位值

    for phase in phases:

        if phase not in PHASE_WEIGHTS:

            raise ValueError(f"无效相位 '{phase}'，有效值：{list(PHASE_WEIGHTS.keys())}")


    cycle_weights_map = {

        kitchin_phase: CYCLE_CONFIG["kitchin"]["weight"],

        juglar_phase: CYCLE_CONFIG["juglar"]["weight"],

        kuznets_phase: CYCLE_CONFIG["kuznets"]["weight"],

        kontratieff_phase: CYCLE_CONFIG["kontratieff"]["weight"]

    }


    final_portfolio = {"stock": 0.0, "bond": 0.0, "commodity": 0.0, "cash": 0.0}


    for phase, weight in cycle_weights_map.items():

        for asset in final_portfolio:

            final_portfolio[asset] += PHASE_WEIGHTS[phase][asset] * weight


    # 四舍五入到整数百分比

    return {k: round(v * 100) for k, v in final_portfolio.items()}



def adjust_portfolio(portfolio: Dict[str, int],

                     ivix_value: Optional[float] = None,

                     pe_quantile: Optional[float] = None,

                     risk_preference: str = "稳健") -> Dict[str, int]:

    """

    风险调整：波动率因子 + 估值因子 + 风险偏好。


    ivix_value: 中国波指（iVIX）当前值

    pe_quantile: 全A市盈率历史分位（0-100）

    risk_preference: 风险偏好（保守/稳健/激进）

    """

    portfolio = portfolio.copy()


    # 1. 波动率因子：中国波指>30时，现金比例+10%，股票-10%

    if ivix_value is not None and ivix_value > 30:

        portfolio["cash"] += 10

        portfolio["stock"] -= 10


    # 2. 估值因子：全A市盈率分位>80%时，股票-15%，债券+15%

    if pe_quantile is not None and pe_quantile > 80:

        portfolio["stock"] -= 15

        portfolio["bond"] += 15


    # 3. 风险偏好调整

    if risk_preference in RISK_PREFERENCE_ADJUSTMENT:

        adj = RISK_PREFERENCE_ADJUSTMENT[risk_preference]

        for asset in portfolio:

            portfolio[asset] += adj[asset]


    # 确保比例非负且总和为100%

    for k in portfolio:

        portfolio[k] = max(0, portfolio[k])

    total = sum(portfolio.values())

    if total > 0:

        portfolio = {k: round(v / total * 100) for k, v in portfolio.items()}


    return portfolio



def calculate_phase_deviation(phases: Dict[str, str]) -> float:

    """

    计算四周期相位偏离度（标准差）。

    标准差越大，周期错位越严重，应增加现金比例。

    """

    import numpy as np

    values = [PHASE_VALUES[phases[cycle]] for cycle in ["kitchin", "juglar", "kuznets", "kontratieff"]]

    return float(np.std(values))



def determine_resonance_strength(phases: Dict[str, str]) -> Dict:

    """

    判断共振强度。

    """

    phase_list = list(phases.values())

    unique_phases = set(phase_list)


    if len(unique_phases) == 1:

        strength = "强共振"

        stars = "★★★★★"

        description = "四周期同相，极端配置，重仓单一方向"

    elif len(unique_phases) == 2:

        # 检查是否有三周期同相

        counts = {p: phase_list.count(p) for p in unique_phases}

        max_count = max(counts.values())

        if max_count == 3:

            strength = "中共振"

            stars = "★★★☆☆"

            description = "三周期同相，适度偏配，有明确方向"

        else:

            strength = "弱共振"

            stars = "★★☆☆☆"

            description = "两两分裂，均衡配置，降低仓位波动"

    else:

        strength = "弱共振"

        stars = "★☆☆☆☆"

        description = "多周期分裂，高度均衡配置，降低风险"


    return {

        "strength": strength,

        "stars": stars,

        "unique_phases": len(unique_phases),

        "description": description

    }



def check_rebalance(current_portfolio: Dict[str, int],

                    last_portfolio: Dict[str, int],

                    threshold: int = 10) -> Dict:

    """

    检查是否需要调仓。


    threshold: 偏离度阈值（默认10%），超过则建议调仓

    """

    deviation = 0

    instructions = []


    for asset in current_portfolio:

        diff = current_portfolio[asset] - last_portfolio.get(asset, 0)

        deviation += abs(diff)

        if abs(diff) >= 3:  # 单资产变动超过3%就生成指令

            action = "买入" if diff > 0 else "卖出"

            instructions.append(f"{action} {abs(diff)}% {ASSET_NAMES[asset]}")


    return {

        "need_rebalance": deviation > threshold,

        "deviation": deviation,

        "threshold": threshold,

        "instructions": instructions,

        "strategy": "大幅调仓" if deviation > threshold else "微调或维持"

    }



def allocate_industries(stock_weight: int,

                        industry_rank: List[Dict]) -> Dict:

    """

    基于行业景气度排名分配股票仓位到具体行业。


    stock_weight: 股票总仓位百分比（如45）

    industry_rank: 行业景气度排序列表，每个元素含 '行业' 和 '景气度' 字段

    """

    if not industry_rank:

        return {"超配": {}, "标配": {}, "低配": {}}


    n = len(industry_rank)

    super_n = min(5, n)

    standard_n = min(10, max(0, n - super_n - min(5, n - super_n)))

    under_n = min(5, max(0, n - super_n - standard_n))


    super_industries = industry_rank[:super_n]

    standard_industries = industry_rank[super_n:super_n + standard_n]

    under_industries = industry_rank[-under_n:] if under_n > 0 else []


    super_weight = round(stock_weight * 0.60 / max(super_n, 1), 1)

    standard_weight = round(stock_weight * 0.30 / max(standard_n, 1), 1)

    under_weight = round(stock_weight * 0.10 / max(under_n, 1), 1)


    return {

        "超配": {item['行业']: super_weight for item in super_industries},

        "标配": {item['行业']: standard_weight for item in standard_industries},

        "低配": {item['行业']: under_weight for item in under_industries}

    }



def generate_monthly_report(kitchin_phase: str, juglar_phase: str,

                             kuznets_phase: str, kontratieff_phase: str,

                             ivix_value: Optional[float] = None,

                             pe_quantile: Optional[float] = None,

                             risk_preference: str = "稳健",

                             last_portfolio: Optional[Dict[str, int]] = None,

                             industry_rank: Optional[List[Dict]] = None) -> str:

    """

    生成完整的月度配置报告（Markdown 格式）。

    """

    phases = {

        "kitchin": kitchin_phase,

        "juglar": juglar_phase,

        "kuznets": kuznets_phase,

        "kontratieff": kontratieff_phase

    }


    # 计算配置

    portfolio = calculate_portfolio(kitchin_phase, juglar_phase, kuznets_phase, kontratieff_phase)

    adjusted = adjust_portfolio(portfolio, ivix_value, pe_quantile, risk_preference)

    resonance = determine_resonance_strength(phases)

    deviation = calculate_phase_deviation(phases)


    # 调仓提醒

    rebalance_info = None

    if last_portfolio:

        rebalance_info = check_rebalance(adjusted, last_portfolio)


    # 行业配置

    industry_alloc = None

    if industry_rank:

        industry_alloc = allocate_industries(adjusted["stock"], industry_rank)


    now = datetime.now().strftime("%Y-%m-%d")


    report = f"""# Deep Fusion 月度资产配置报告


**生成日期**：{now}

**算法**：四周期加权共振法

**风险偏好**：{risk_preference}


---


## 一、四周期当前状态


| 周期 | 当前相位 | 权重 | 作用 |

|------|---------|------|------|

| 基钦周期（库存） | {kitchin_phase} | 40% | 决定短期战术仓位 |

| 朱格拉周期（设备） | {juglar_phase} | 30% | 决定中期战略方向 |

| 库兹涅茨周期（房地产） | {kuznets_phase} | 20% | 决定大类资产长期偏好 |

| 康波周期（技术） | {kontratieff_phase} | 10% | 决定超长期资产底色 |


**共振强度**：{resonance['stars']} {resonance['strength']}

**相位偏离度**：{deviation:.1f}（标准差越大，错位越严重）

**说明**：{resonance['description']}


---


## 二、大类资产配置建议


| 资产类别 | 配置比例 | 资产中文名 |

|---------|---------|-----------|

| 股票 | **{adjusted['stock']}%** | 股票 |

| 债券 | **{adjusted['bond']}%** | 债券 |

| 商品 | **{adjusted['commodity']}%** | 商品 |

| 现金 | **{adjusted['cash']}%** | 现金 |


"""


    if ivix_value is not None:

        report += f"**风险因子**：iVIX={ivix_value}{'（⚠ 超过30阈值，现金比例已上调）' if ivix_value > 30 else ''}\n"

    if pe_quantile is not None:

        report += f"**估值因子**：全A市盈率分位={pe_quantile}%{'（⚠ 超过80%阈值，股票比例已下调）' if pe_quantile > 80 else ''}\n"


    report += "\n---\n\n"


    if industry_alloc:

        report += "## 三、行业配置建议\n\n"

        report += "### 🔥 超配行业\n\n"

        for ind, w in industry_alloc["超配"].items():

            report += f"- **{ind}**：{w}%\n"

        report += "\n### 📊 标配行业\n\n"

        for ind, w in industry_alloc["标配"].items():

            report += f"- {ind}：{w}%\n"

        report += "\n### ❄ 低配行业\n\n"

        for ind, w in industry_alloc["低配"].items():

            report += f"- {ind}：{w}%\n"

        report += "\n---\n\n"


    if rebalance_info:

        report += "## 四、调仓提醒\n\n"

        report += f"**偏离度**：{rebalance_info['deviation']}%\n"

        report += f"**调仓策略**：{rebalance_info['strategy']}\n"

        if rebalance_info['instructions']:

            report += "\n**具体指令**：\n\n"

            for inst in rebalance_info['instructions']:

                report += f"- {inst}\n"

        else:

            report += "\n✅ 当前配置与建议偏离度较小，无需调仓。\n"

        report += "\n---\n\n"


    report += """## 五、下月关键跟踪指标


- 基钦周期相位是否切换（关注库存数据）

- 全A市盈率分位变化（关注估值泡沫风险）

- iVIX波动率指数（关注市场恐慌情绪）

- 央行货币政策动向（利率调整影响债券配置）


---


*本报告由 Deep Fusion 四周期嵌套资产配置引擎自动生成，仅供参考，不构成投资建议。*

"""


    return report



# ============================================================

# 3. CLI 入口

# ============================================================


def main():

    """命令行入口，支持多种计算模式。"""

    if len(sys.argv) < 2:

        print("用法: python cycle_allocator.py <command> [args...]")

        print()

        print("命令:")

        print("  portfolio <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

        print("         计算资产配置比例")

        print("  adjust <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位> [ivix] [pe分位] [风险偏好]")

        print("         风险调整后的配置比例")

        print("  resonance <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

        print("         判断共振强度")

        print("  report <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

        print("         生成完整月度报告")

        print()

        print("相位有效值: 复苏, 繁荣, 衰退, 萧条")

        print("风险偏好: 保守, 稳健, 激进")

        sys.exit(1)


    command = sys.argv[1]


    if command == "portfolio":

        if len(sys.argv) < 6:

            print("用法: portfolio <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

            sys.exit(1)

        result = calculate_portfolio(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

        print(json.dumps(result, ensure_ascii=False, indent=2))


    elif command == "adjust":

        if len(sys.argv) < 6:

            print("用法: adjust <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位> [ivix] [pe分位] [风险偏好]")

            sys.exit(1)

        portfolio = calculate_portfolio(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

        ivix = float(sys.argv[6]) if len(sys.argv) > 6 else None

        pe = float(sys.argv[7]) if len(sys.argv) > 7 else None

        risk = sys.argv[8] if len(sys.argv) > 8 else "稳健"

        result = adjust_portfolio(portfolio, ivix, pe, risk)

        print(json.dumps(result, ensure_ascii=False, indent=2))


    elif command == "resonance":

        if len(sys.argv) < 6:

            print("用法: resonance <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

            sys.exit(1)

        phases = {"kitchin": sys.argv[2], "juglar": sys.argv[3],

                  "kuznets": sys.argv[4], "kontratieff": sys.argv[5]}

        result = determine_resonance_strength(phases)

        deviation = calculate_phase_deviation(phases)

        result["deviation"] = round(deviation, 2)

        print(json.dumps(result, ensure_ascii=False, indent=2))


    elif command == "report":

        if len(sys.argv) < 6:

            print("用法: report <基钦相位> <朱格拉相位> <库兹涅茨相位> <康波相位>")

            sys.exit(1)

        report = generate_monthly_report(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

        print(report)


    else:

        print(f"未知命令: {command}")

        sys.exit(1)



if __name__ == "__main__":

    main()