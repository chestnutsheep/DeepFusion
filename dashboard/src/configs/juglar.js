export const JUGLAR_CONFIG = {
  queryKey: 'data_juglar',
  extQueryKey: 'data_juglar_extended',
  title: '朱格拉周期',
  icon: '📈',
  phaseField: 'phase_name',
  chartSeries: [
    { key: 'composite_z', name: '合成Z值', color: '#4e6cce', type: 'line' },
    { key: 'cycle_val', name: '周期分量', color: '#c1a332', type: 'line' },
  ],
  nbsChartSeries: [
    { key: 'comp_z', name: '综合Z值', color: '#4e6cce', type: 'line' },
    { key: 'fix_inv_yoy', name: '固定资产投资', color: '#c1a332', type: 'line' },
  ],
  metrics: [
    { key: 'comp_z', label: '综合z值', unit: '', dir: true, card: true, decimals: 4, higherBetter: true },
    { key: 'fix_inv_yoy', label: '固定资产投资', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true },
    { key: 'capacity_util', label: '产能利用率', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true },
    { key: 'manufacturing_yoy', label: '制造业投资', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true },
  ],
};
