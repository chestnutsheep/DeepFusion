export const MACRO_SNAPSHOT_CONFIG = [
  { key: 'gdp', label: 'GDP当季同比', unit: '%', decimals: 1, higherBetter: true, source: 'macro_gdp' },
  { key: 'cpi', label: 'CPI当月同比', unit: '%', decimals: 1, higherBetter: false, source: 'macro_cpi' },
  { key: 'pmi', label: '制造业PMI', unit: '', decimals: 1, higherBetter: true, source: 'macro_pmi' },
  { key: 'inventory', label: '产成品库存', unit: '%', decimals: 1, higherBetter: null, source: 'macro_inventory_growth' },
];