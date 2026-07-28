import DataCard from './DataCard.jsx';

export default function DataGrid({ config, data, prevData, columns = 3, gap = 'var(--sp-lg)', containerStyle, square = false }) {
  if (!data) return null;
  const items = config.map(cfg => {
    let value = data[cfg.key];
    if (cfg.transform && value != null) value = cfg.transform(value);
    return {
      ...cfg,
      value,
      prevValue: prevData?.[cfg.key],
    };
  });
  // 响应式列数：≤4列保持原样，>4列在窄屏降级
  const responsiveClass = columns > 3 ? 'data-grid-4col' : '';
  const mobileClass = columns > 2 ? 'data-grid-responsive' : '';
  return (
    <div
      className={`data-grid-responsive ${responsiveClass} ${mobileClass}`}
      style={{
        display: 'grid',
        gridTemplateColumns: square
          ? `repeat(${columns}, minmax(130px, 190px))`
          : `repeat(${columns}, 1fr)`,
        gap,
        ...(square ? { justifyContent: 'center' } : {}),
        ...containerStyle,
      }}
    >
      {items.map((item, i) => {
        const { key: _key, transform: _transform, ...cardProps } = item;
        return <DataCard key={i} square={square} {...cardProps} />;
      })}
    </div>
  );
}
