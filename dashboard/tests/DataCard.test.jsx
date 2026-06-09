import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataCard from '../src/components/common/DataCard';

describe('DataCard 组件', () => {
  it('渲染标签和值', () => {
    render(<DataCard label="GDP" value={5.2} />);
    expect(screen.getByText('GDP')).toBeInTheDocument();
    expect(screen.getByText('5.2')).toBeInTheDocument();
  });

  it('显示单位', () => {
    render(<DataCard label="CPI" value={2.1} unit="%" />);
    expect(screen.getByText('%')).toBeInTheDocument();
  });

  it('null 值显示 —', () => {
    render(<DataCard label="PMI" value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('undefined 值显示 —', () => {
    render(<DataCard label="PMI" value={undefined} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('highetBetter=true + 上升 → 数值白色，箭头绿色', () => {
    render(<DataCard label="GDP" value={5.2} prevValue={4.0} higherBetter />);
    const valueSpan = screen.getByText('5.2');
    expect(valueSpan.style.color).toBe('var(--text-primary)');
    const arrow = screen.getByText('↑');
    expect(arrow.style.color).toBe('#3fb950');
  });

  it('highetBetter=true + 下降 → 数值白色，箭头红色', () => {
    render(<DataCard label="GDP" value={4.0} prevValue={5.2} higherBetter />);
    expect(screen.getByText('↓')).toBeInTheDocument();
    const valueSpan = screen.getByText('4.0');
    expect(valueSpan.style.color).toBe('var(--text-primary)');
  });

  it('highetBetter=false + 下降 → 数值白色，箭头绿色（逆向指标）', () => {
    render(<DataCard label="失业率" value={4.0} prevValue={5.2} higherBetter={false} />);
    const arrow = screen.getByText('↓');
    expect(arrow.style.color).toBe('#3fb950');
  });

  it('highetBetter=null + 有方向 → 数值白色，箭头金色', () => {
    render(<DataCard label="M2" value={8.5} prevValue={7.0} higherBetter={null} />);
    const valueSpan = screen.getByText('8.5');
    expect(valueSpan.style.color).toBe('var(--text-primary)');
    const arrow = screen.getByText('↑');
    expect(arrow.style.color).toBe('var(--accent-gold)');
  });

  it('无方向且 highetBetter=null → 数值金色', () => {
    render(<DataCard label="M2" value={8.5} higherBetter={null} />);
    const valueSpan = screen.getByText('8.5');
    expect(valueSpan.style.color).toBe('var(--accent-gold)');
  });

  it('显示来源信息', () => {
    render(<DataCard label="GDP" value={5.2} source="国家统计局" />);
    expect(screen.getByText(/国家统计局/)).toBeInTheDocument();
  });

  it('使用指定小数位', () => {
    render(<DataCard label="GDP" value={5.6789} decimals={2} />);
    expect(screen.getByText('5.68')).toBeInTheDocument();
  });

  it('无 prevValue 时不显示方向', () => {
    render(<DataCard label="GDP" value={5.2} />);
    expect(screen.queryByText('↑')).not.toBeInTheDocument();
    expect(screen.queryByText('↓')).not.toBeInTheDocument();
  });
});
