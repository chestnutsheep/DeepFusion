export const KONDRATIEV_CONFIG = {
  queryKey: 'data_kondratiev',
  extQueryKey: null,
  title: '康波周期',
  icon: '🌊',
  phaseField: 'phase',
  params: { method: 'pca' },
  chartSeries: [
    { key: 'global_intensity', name: '全球周期', color: '#42a2dc', type: 'line', yAxisIndex: 0 },
    { key: 'china_intensity', name: '中国周期', color: '#e74c3c', type: 'line', yAxisIndex: 0 },
    { key: 'intensity', name: '融合强度', color: '#D4A853', type: 'line', yAxisIndex: 1 },
  ],
  // 三种计算方法逐一对比，detail 填充悬浮解释文本
  methodMetrics: [
    { method: 'pca', label: 'PCA频谱法', decimals: 1, higherBetter: true,
      detail: '通过带通滤波(40-70年)提取PCA合成指数主成分，结合历史拐点加权判定当前康波相位。置信度基于指标内一致性评分。' },
    { method: 'wavelet', label: '小波分析法', decimals: 1, higherBetter: true,
      detail: '对PCA主成分序列进行Morlet连续小波变换，通过时频能量谱的相位角确定康波周期位置,置信度基于小波功率谱密度。' },
    { method: 'bandpass', label: '带通滤波法', decimals: 1, higherBetter: true,
      detail: '采用Butterworth带通滤波器(40-70年)从PCA序列中提取长波成分,通过波形零交叉点和极值确定相位,置信度基于滤波残差。' },
  ],
  metrics: [
    { key: 'phase_name', label: '融合相位', unit: '', dir: false, card: true, decimals: 0, higherBetter: null },
    { key: 'global_phase_name', label: '全球相位', unit: '', dir: false, card: true, decimals: 0, higherBetter: null },
    { key: 'china_phase_name', label: '中国相位', unit: '', dir: false, card: true, decimals: 0, higherBetter: null },
    { key: 'confidence', label: '综合置信度', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true, transform: v => (v * 100).toFixed(1) },
    { key: 'turning_probability', label: '拐点概率', unit: '%', dir: false, card: true, decimals: 1, higherBetter: null, transform: v => (v * 100).toFixed(1) },
    { key: 'dominant_period', label: '主周期', unit: '年', dir: false, card: true, decimals: 1, higherBetter: null },
    { key: 'pca_variance_ratio', label: 'PCA解释度', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true, transform: v => v * 100 },
  ],
};
