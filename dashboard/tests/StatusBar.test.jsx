import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBar from '../src/components/common/StatusBar';

describe('StatusBar 组件', () => {
  it('渲染当前周期状态标题', () => {
    render(<StatusBar />);
    expect(screen.getByText('当前周期状态')).toBeInTheDocument();
  });

  it('显示阶段名称', () => {
    render(<StatusBar phase="复苏" period="202601" />);
    expect(screen.getByText('复苏')).toBeInTheDocument();
  });

  it('显示数据截至时间', () => {
    render(<StatusBar phase="繁荣" period="202602" />);
    expect(screen.getByText(/数据截至 202602/)).toBeInTheDocument();
  });

  it('不传 phase 时不显示阶段标记', () => {
    render(<StatusBar />);
    expect(screen.getByText('当前周期状态')).toBeInTheDocument();
    expect(screen.queryByText(/数据截至/)).not.toBeInTheDocument();
  });

  it('支持自定义颜色', () => {
    render(<StatusBar phase="衰退" period="202603" color="#ff6b6b" />);
    const badge = screen.getByText('衰退');
    expect(badge.style.background).toBe('#ff6b6b');
  });

  it('默认颜色金色', () => {
    render(<StatusBar phase="复苏" period="202601" />);
    const badge = screen.getByText('复苏');
    expect(badge.style.background).toBe('var(--accent-gold)');
  });
});