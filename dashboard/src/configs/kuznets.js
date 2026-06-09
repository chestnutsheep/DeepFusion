export const KUZNETS_CONFIG = {
  queryKey: 'data_kuznets',
  title: '库兹涅茨周期',
  icon: '🏠',
  phaseField: 'phase_name',
  chartSeries: [
    { key: 'house_price_yoy', name: '房价同比', color: '#d2991d', type: 'line' },
    { key: 'sales_yoy', name: '销售面积同比', color: '#58a6ff', type: 'line' },
  ],
  metrics: [
    { key: 'house_price_yoy', label: '房价同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true },
    { key: 'sales_yoy', label: '销售面积同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true },
    { key: 'new_start_yoy', label: '新开工同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true },
  ],
};