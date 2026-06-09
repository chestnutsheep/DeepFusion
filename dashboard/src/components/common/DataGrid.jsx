import DataCard from './DataCard.jsx';

export default function DataGrid({ config, data, prevData, columns = 3, gap = 16 }) {
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
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap }}>
      {items.map((item, i) => {
        const { key: _key, transform: _transform, ...cardProps } = item;
        return <DataCard key={i} {...cardProps} />;
      })}
    </div>
  );
}
