export const KITCHIN_CONFIG = {
  queryKey: 'data_kitchin',
  extQueryKey: 'data_kitchin_extended',
  title: '基钦周期',
  icon: '📉',
  phaseField: 'stage_name',
  // 扩展数据（FRED）绘图系列 — 优先使用
  chartSeries: [
    { key: 'composite_z', name: '合成Z值', color: '#D4A853', type: 'line' },
    { key: 'cycle_val', name: '周期分量', color: '#5bba57', type: 'line' },
  ],
  // NBS 月频数据绘图系列 — 扩展数据不可用时的回退
  nbsChartSeries: [
    { key: 'inventory_yoy', name: '库存同比', color: '#D4A853', type: 'line' },
    { key: 'demand_yoy', name: '需求同比', color: '#5bba57', type: 'line' },
  ],
  metrics: [
    { key: 'inventory_yoy', label: '库存同比', unit: '%', dir: true, card: true, higherBetter: null, decimals: 1 },
    { key: 'demand_yoy', label: '需求同比', unit: '%', dir: true, card: true, higherBetter: true, decimals: 1 },
    { key: 'pmi', label: 'PMI', unit: '', dir: false, card: true, higherBetter: true, decimals: 1 },
    { key: 'm2_yoy', label: 'M2同比', unit: '%', dir: false, card: true, higherBetter: null, decimals: 1 },
    { key: 'real_inventory_yoy', label: '实际库存同比', unit: '%', dir: true, card: true, higherBetter: null, decimals: 1 },
  ],
};
