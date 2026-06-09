import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataGrid from '../src/components/common/DataGrid';

describe('DataGrid 组件', () => {
  const config = [
    { key: 'gdp', label: 'GDP当季同比', unit: '%' },
    { key: 'cpi', label: 'CPI同比', unit: '%', higherBetter: false },
    { key: 'pmi', label: 'PMI' },
    { key: 'inv', label: '库存', unit: '%', higherBetter: null },
  ];

  it('渲染配置中的所有卡片', () => {
    const data = { gdp: 6.7, cpi: 2.0, pmi: 50.1, inv: 5.2 };
    render(<DataGrid config={config} data={data} />);
    expect(screen.getByText('GDP当季同比')).toBeInTheDocument();
    expect(screen.getByText('CPI同比')).toBeInTheDocument();
    expect(screen.getByText('PMI')).toBeInTheDocument();
    expect(screen.getByText('库存')).toBeInTheDocument();
    expect(screen.getByText('6.7')).toBeInTheDocument();
    expect(screen.getByText('2.0')).toBeInTheDocument();
  });

  it('data 为 null 时不渲染', () => {
    const { container } = render(<DataGrid config={config} data={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('缺少某些字段的 data 仍渲染', () => {
    const data = { gdp: 6.7, cpi: 2.0 }; // 缺失 pmi, inv
    render(<DataGrid config={config} data={data} />);
    expect(screen.getByText('GDP当季同比')).toBeInTheDocument();
    expect(screen.getByText('CPI同比')).toBeInTheDocument();
    expect(screen.getByText('PMI')).toBeInTheDocument();
    // 缺失字段显示 —
    expect(screen.getAllByText('—')).toHaveLength(2); // PMI 和 库存 为 —
  });

  it('使用 prevData 计算方向', () => {
    const data = { gdp: 6.7, cpi: 2.0, pmi: 50.1, inv: 5.2 };
    const prevData = { gdp: 6.0, cpi: 1.8, pmi: 49.0, inv: 5.5 };
    render(<DataGrid config={config} data={data} prevData={prevData} />);
    // GDP 上升，higherBetter 默认 true → 绿色 ↑
    // CPI 上升，higherBetter=false → 红色 ↑
    // PMI 上升，higherBetter 默认 true → 绿色 ↑
    // INV 下降，higherBetter=null → 金色 ↓
    expect(screen.getAllByText('↑')).toHaveLength(3); // GDP、CPI、PMI
    expect(screen.getByText('↓')).toBeInTheDocument(); // INV
  });

  it('支持 transform 函数', () => {
    const customConfig = [
      { key: 'value', label: '指标', transform: v => v.toFixed(0) },
    ];
    const data = { value: 5.6789 };
    render(<DataGrid config={customConfig} data={data} />);
    expect(screen.getByText('6')).toBeInTheDocument(); // 四舍五入
  });

  it('transform 不处理 null', () => {
    const customConfig = [
      { key: 'value', label: '指标', transform: v => v * 100 },
    ];
    const data = { value: null };
    render(<DataGrid config={customConfig} data={data} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('自定义列数和间距', () => {
    const data = { gdp: 6.7, cpi: 2.0 };
    const { container } = render(
      <DataGrid config={config.slice(0, 2)} data={data} columns={2} gap={30} />
    );
    const grid = container.firstChild;
    expect(grid).toHaveStyle({
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '30px',
    });
  });

  it('默认 3 列', () => {
    const data = { gdp: 6.7, cpi: 2.0, pmi: 50.1 };
    const { container } = render(<DataGrid config={config.slice(0, 3)} data={data} />);
    const grid = container.firstChild;
    expect(grid).toHaveStyle({
      gridTemplateColumns: 'repeat(3, 1fr)',
    });
  });
});