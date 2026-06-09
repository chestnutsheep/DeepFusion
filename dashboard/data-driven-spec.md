# DeepFusion 数据驱动渲染架构

> 目标：零手动维护。所有数值、趋势、阶段名全部从 MCP 数据自动渲染。

---

## 1. 配置表 Schema

每个模块的指标配置 = 一个 JS 数组，附在 `configs/` 下：

```js
// configs/kitchin.js
export const KITCHIN_METRICS = [
  {
    key: 'inventory_yoy',        // data_kitchin JSON 字段名
    label: '库存同比',           // 显示文字
    unit: '%',                   // 单位后缀
    dir: true,                   // 显示 ↑↓ 箭头（对比上期）
    card: true,                  // 在面板卡中显示
    chart: true,                 // 在主图表中显示
    chartType: 'line',           // line | bar
    higherBetter: null,          // true=红色向上, false=绿色向下, null=金色
    decimals: 1,                 // 小数位数
  },
  { key: 'demand_yoy',      label: '需求同比',       unit: '%',  dir: true,  card: true,  chart: true,  higherBetter: true },
  { key: 'pmi',             label: 'PMI',             unit: '',   dir: false, card: true,  chart: false, higherBetter: true },
  { key: 'real_inventory_yoy', label: '实际库存同比',  unit: '%',  dir: true,  card: true,  chart: false, higherBetter: null },
  { key: 'm2_yoy',          label: 'M2同比',          unit: '%',  dir: false, card: true,  chart: false },
]
```

```js
// configs/juglar.js
export const JUGLAR_METRICS = [
  { key: 'comp_z',         label: '综合z值',         unit: '',  dir: true,  card: true,  chart: true,  decimals: 4, higherBetter: true },
  { key: 'fix_inv_yoy',    label: '固定投资',         unit: '%', dir: true,  card: true,  chart: true,  higherBetter: true },
  { key: 'capacity_util',  label: '产能利用率',       unit: '%', dir: false, card: true,  chart: false, higherBetter: true },
  { key: 'manufacturing_yoy', label: '制造业投资',    unit: '%', dir: false, card: true,  chart: false },
]
```

## 2. 组件层次

```
<CyclePage>                    ← 宏观周期页的外壳
  ├─ <StatusBar>               ← 阶段名 + 色标 + 数据期间
  ├─ <DataChart>               ← ECharts 折线/柱状图
  └─ <DataGrid>                ← 指标卡网格
       └─ <DataCard> × N      ← 单个指标卡

<MetricGrid>                   ← 通用指标网格（非周期模块用）
  └─ <DataCard> × N

<DataCard>                     ← 最小可复用单位
  └─ (future) <DetailPopover>  ← @floating-ui/react 悬浮详情
```

## 3. 组件 Props 定义

### DataCard

```jsx
<DataCard
  label="库存同比"          // 显示名称
  value={6.7}              // 数值
  prevValue={5.2}          // 上期值（用于计算方向）
  unit="%"                 // 单位
  dir="up"                 // "up"|"down"|null（自动从 prevValue 算）
  decimals={1}             // 小数位
  detail="剔除价格后4.6%"  // 悬浮卡详细说明（可选）
  source="NBS"             // 数据来源标签（可选）
/>
```

### DataChart

```jsx
<DataChart
  data={rows}                    // [{ period, inventory_yoy, demand_yoy }]
  series={[
    { key: 'inventory_yoy', name: '库存', color: '#f85149', type: 'line' },
    { key: 'demand_yoy',    name: '需求', color: '#D4A853', type: 'line' },
  ]}
  dateKey="period"               // 日期字段
  height={320}
  zoom={true}                    // 启用 dataZoom
/>
```

### DataGrid

```jsx
<DataGrid
  config={KITCHIN_METRICS}       // 指标配置数组
  data={latestRow}               // 最新一期数据对象
  prevData={prevRow}             // 上期（用于算方向）
  columns={3}                    // 列数
  cardComponent={DataCard}       // 可注入自定义卡片组件
/>
```

## 4. 通用 CyclePage（四周期共用）

```jsx
function CyclePage({ title, icon, config, queryKey, phaseField, chartSeries }) {
  const { data } = useQueryMCPJSON(queryKey);
  const rows = Array.isArray(data) ? data : [];
  const latest = rows[rows.length - 1] || {};
  const prev = rows[rows.length - 2] || {};

  return (
    <div>
      <StatusBar phase={latest[phaseField]} period={latest.period} />
      <DataChart data={rows} series={chartSeries} dateKey="period" />
      <DataGrid config={config} data={latest} prevData={prev} />
    </div>
  );
}
```

使用：

```jsx
<CyclePage
  title="基钦周期"
  icon="📉"
  config={KITCHIN_METRICS}
  queryKey="data_kitchin"
  phaseField="stage_name"
  chartSeries={[
    { key: 'inventory_yoy', name: '库存', color: '#f85149' },
    { key: 'demand_yoy',    name: '需求', color: '#D4A853' },
  ]}
/>
```

## 5. 各模块配置表清单

| 模块 | 配置文件名 | 数据工具 | 核心字段 |
|------|-----------|---------|---------|
| 基钦 | configs/kitchin.js | data_kitchin | inventory_yoy, demand_yoy, pmi |
| 朱格拉 | configs/juglar.js | data_juglar | comp_z, fix_inv_yoy, capacity_util |
| 库兹涅茨 | configs/kuznets.js | data_kuznets | house_price_yoy, sales_yoy, new_start_yoy |
| 康波 | configs/kondratiev.js | data_kondratiev | pca1, dominant_period, confidence |
| 宏观快照 | configs/macro-snapshot.js | macro_gdp/cpi/pmi | GDP, CPI, PMI, 库存, 固投 |
| 中观行业 | configs/industry.js | industry_daily_query | close, volume |
| 个股财务 | configs/stock-finance.js | financial_indicators | 营收增长率, ROE, 毛利率 |
| 资金流 | configs/capital-flow.js | capital_tracking | 主力净流入, 日期 |
| 国际 | configs/global.js | fred_data, wb_data | date, value |

## 6. 实现顺序（按优先级）

| 步骤 | 内容 | 涉及文件 |
|------|------|---------|
| 1 | `DataCard` 组件 | components/charts/DataCard.jsx |
| 2 | `DataGrid` 组件 | components/charts/DataGrid.jsx |
| 3 | `DataChart` 组件（通用化现有） | components/charts/DataChart.jsx |
| 4 | `StatusBar` 组件 | components/charts/StatusBar.jsx |
| 5 | 四周期配置表 | configs/kitchin.js, juglar.js, kuznets.js, kondratiev.js |
| 6 | `CyclePage` 通用页 | components/Macro/CyclePage.jsx |
| 7 | 用 CyclePage 替换四个 Tab | MacroLayout 只保留一份 CyclePage + 配置切换 |
| 8 | 宏观快照改用 DataGrid | MacroSnapshot.jsx |
| 9 | 中观改用 DataGrid + DataChart | MesoTab.jsx |
| 10 | 微观财务卡改用 DataGrid | StockPanel.jsx |

## 7. 技术要点

- **DataCard 颜色规则**：`higherBetter=true` 且方向↑ → 红色；`higherBetter=false` 且方向↓ → 绿色；`higherBetter=null` → 金色
- **方向计算**：`dir = value > prevValue ? 'up' : 'down'`（或在 DataGrid 层面自动算）
- **悬浮卡**：`detail` 非空时自动启用 `@floating-ui/react` 的 `useFloating` + `autoUpdate`
- **空值处理**：`value == null` → 显示 "—"
- **图表 dataZoom**：DataChart 默认启用 `inside` 滚轮缩放
