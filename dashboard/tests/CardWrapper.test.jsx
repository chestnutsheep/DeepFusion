import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CardWrapper from '../src/components/common/CardWrapper';

describe('CardWrapper', () => {
  it('渲染子元素', () => {
    render(<CardWrapper><span>内容</span></CardWrapper>);
    expect(screen.getByText('内容')).toBeInTheDocument();
  });

  it('默认有金边和毛玻璃样式', () => {
    const { container } = render(<CardWrapper>test</CardWrapper>);
    const el = container.firstChild;
    // happy-dom 不解析 CSS 自定义属性，只验证静态值
    expect(el).toHaveStyle('backdrop-filter: blur(8px)');
    expect(el).toHaveStyle('border: 1px solid rgba(212,168,83,0.5)');
    expect(el).toHaveStyle('border-radius: 2px');
  });

  it('truncate 模式设置 overflow hidden', () => {
    const { container } = render(<CardWrapper truncate>长文本</CardWrapper>);
    expect(container.firstChild).toHaveStyle('overflow: hidden');
    expect(container.firstChild).toHaveStyle('white-space: nowrap');
    expect(container.firstChild).toHaveStyle('text-overflow: ellipsis');
  });

  it('as="a" 渲染为 <a>', () => {
    render(<CardWrapper as="a" href="https://test.com">链接</CardWrapper>);
    const link = screen.getByText('链接');
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', 'https://test.com');
  });

  it('hoverable=true 且无 href 时 cursor=default', () => {
    const { container } = render(<CardWrapper hoverable>内容</CardWrapper>);
    expect(container.firstChild).toHaveStyle('cursor: default');
  });

  it('hoverable=true 且有 href 时 cursor=pointer', () => {
    const { container } = render(<CardWrapper as="a" href="https://x.com">链接</CardWrapper>);
    expect(container.firstChild).toHaveStyle('cursor: pointer');
  });

  it('hoverable=false 时无特殊 cursor', () => {
    const { container } = render(<CardWrapper hoverable={false}>内容</CardWrapper>);
    expect(container.firstChild).not.toHaveStyle('cursor: pointer');
  });

  it('接受自定义 style 合并', () => {
    const { container } = render(<CardWrapper style={{ marginTop: 20 }}>内容</CardWrapper>);
    expect(container.firstChild).toHaveStyle('margin-top: 20px');
  });
});
