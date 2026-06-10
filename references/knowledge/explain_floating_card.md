---
tags:
  - Design
  - 注释
  - 组件
  - floating
---
为供一个**可复用的悬浮解释性文本组件**，基于 `@floating-ui/react`。可以在任何 `DataCard`、图表图例、指标名称旁添加一个“ⓘ”图标，悬浮时显示解释文案。

---

## 一、组件代码：`TooltipIcon.jsx`

```jsx
// src/components/common/TooltipIcon.jsx
import { useFloating, autoUpdate, offset, shift, useHover, useInteractions } from '@floating-ui/react';
import { useState } from 'react';

/**
 * 悬浮解释图标组件
 * @param {string} content - 解释文本（支持 HTML 字符串或纯文本）
 * @param {string} [position="top"] - 提示框位置：top / bottom / left / right
 * @param {React.ReactNode} [children] - 自定义图标（默认显示 ⓘ）
 */
export default function TooltipIcon({ content, position = 'top', children }) {
  const [isOpen, setIsOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: position,
    middleware: [offset(8), shift()],
    whileElementsMounted: autoUpdate,
  });
  const hover = useHover(context);
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);

  return (
    <>
      <span
        ref={refs.setReference}
        {...getReferenceProps()}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          cursor: 'help',
          marginLeft: 4,
          fontSize: 12,
          color: 'var(--text-muted)',
        }}
      >
        {children || 'ⓘ'}
      </span>
      {isOpen && (
        <div
          ref={refs.setFloating}
          style={{
            ...floatingStyles,
            background: 'var(--bg-sidebar)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius)',
            padding: '8px 12px',
            maxWidth: 260,
            fontSize: 12,
            lineHeight: 1.5,
            color: 'var(--text-secondary)',
            zIndex: 1000,
            boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
          }}
          {...getFloatingProps()}
        >
          {content}
        </div>
      )}
    </>
  );
}
```

---

## 二、在 `DataCard` 中集成（自动显示每个指标的解释）

修改的 `DataCard.jsx`，在 `label` 旁边加上 `TooltipIcon`：

```jsx
// 在 DataCard.jsx 的头部导入
import TooltipIcon from './TooltipIcon';

// 在渲染 label 的位置修改
<div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
  {tooltip && <TooltipIcon content={tooltip} position="top" />}
</div>
```

然后在配置表中添加 `tooltip` 字段：

```js
// configs/kondratiev.js 示例
{ key: 'confidence', label: '置信度', unit: '%', tooltip: '基于PCA解释度 + 三种周期方法一致性计算。>80%为高置信，<50%表示相位边界模糊。' }
```

---

## 三、单独使用示例（图表图例、周期名称等）

可以在任何地方直接使用 `<TooltipIcon content="解释文字" />`。

```jsx
// 在周期时钟组件中
<span>基钦周期 <TooltipIcon content="库存周期，时长3-5年，决定短期战术仓位" /></span>

// 在图表图例中
<LegendItem>
  策略收益 
  <TooltipIcon content="基于四周期加权共振法计算的模拟收益，已扣除交易成本" />
</LegendItem>
```

---

## 四、预设常用解释文案库（可直接复制到的配置中）

可以将这些文案放在 `src/configs/tooltips.js` 中，方便复用：

```js
export const TOOLTIPS = {
  // 周期相位
  kitchin_phase: '基钦周期（库存）反映企业存货变动，领先经济6-12个月。主动补库存→繁荣，被动去库存→复苏。',
  juglar_phase: '朱格拉周期（设备投资）周期约7-11年，反映制造业资本开支。复苏→繁荣→衰退→萧条循环。',
  kuznets_phase: '库兹涅茨周期（房地产）周期约15-25年，受人口和城镇化驱动。',
  kondratiev_phase: '康波周期（技术革命）周期约50-60年，由重大技术创新推动。当前处于第五波长波的哪个阶段仍有争议。',

  // 周期指标
  inventory_yoy: '工业企业产成品存货同比增速。上升表示企业主动补库存，下降表示去库存。',
  demand_yoy: '工业增加值同比增速，代表需求侧热度。与库存增速结合判断库存周期阶段。',
  comp_z: '朱格拉周期综合z值，由固投、制造业投资、产能利用率等因子合成。>0表示投资景气上行。',
  house_price_yoy: '70大中城市新建住宅价格同比。>0表示房价上涨，房地产周期向上。',

  // 宏观快照
  gdp: '国内生产总值当季同比，反映整体经济增长速度。',
  cpi: '居民消费价格指数同比，衡量通胀水平。>3%警惕过热，<0%警惕通缩。',
  pmi: '制造业采购经理指数，>50表示扩张，<50表示收缩。领先经济3-6个月。',

  // 行业轮动
  industry_momentum: '行业指数近20日涨幅，代表短期资金偏好。结合景气度使用更有效。',
  industry_pe: '行业市盈率(TTM)，估值高低。与历史分位结合判断是否高估。',

  // 资产配置
  portfolio_equity: '股票仓位建议。基于四周期加权共振计算，可根据个人风险偏好调整±10%。',
  portfolio_bond: '债券仓位建议。经济衰退期增加债券，繁荣期降低。',
  portfolio_commodity: '商品仓位建议。基钦繁荣期超配工业金属，康波萧条期超配黄金。',
  portfolio_cash: '现金及货币基金仓位。市场恐慌时（VIX>30）自动增加至30%。',

  // 风险指标
  vix: '中国波指，反映期权市场对未来30天波动的预期。>25表示市场恐慌，>30需警惕风险。',
  pe_quantile: '全A市盈率历史分位数，>80%表示整体估值偏高，应降低股票仓位。',

  // 康波专用
  kondratiev_confidence: '康波相位置信度，基于PCA解释度、小波功率谱峰值强度、历史相位转换准确率综合计算。',
  kondratiev_pca: '第一主成分，由人均GDP、PPI、利率等长周期指标合成。滤波后用于判断康波相位。',
  wavelet_power: '小波功率谱强度，>0.7表示当前时间点处于该周期的强势阶段，周期信号显著。',
  bandpass_value: '40-60年带通滤波值，>0表示康波上升半周期，<0表示下降半周期。',
};
```

然后在配置表中引用：

```js
import { TOOLTIPS } from '../configs/tooltips';

{ key: 'inventory_yoy', label: '库存同比', tooltip: TOOLTIPS.inventory_yoy }
```

---

## 五、样式微调

可以在 `global.css` 中定义悬浮卡片的统一样式（已在组件中内联，也可提取）：

```css
.tooltip-popup {
  background: var(--bg-sidebar);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius);
  padding: 8px 12px;
  max-width: 260px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  z-index: 1000;
}
```

然后在组件中直接使用该类名。

---

## 六、使用效果

- 鼠标移动到 `ⓘ` 图标或带有 `TooltipIcon` 的指标名称上，会弹出毛玻璃风格的黑色卡片，显示解释文本。
- 支持多行文本，可包含链接或简单格式。
- 位置自动适配（`shift` 中间件防止超出边界）。

