import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TooltipIcon from '../src/components/common/TooltipIcon';

describe('TooltipIcon', () => {
  it('渲染 ⓘ 图标', () => {
    render(<TooltipIcon content="测试解释文字" />);
    expect(screen.getByText('ⓘ')).toBeInTheDocument();
  });

  it('悬浮时显示提示文字', async () => {
    const user = userEvent.setup();
    render(<TooltipIcon content="测试解释文字" />);
    await user.hover(screen.getByText('ⓘ'));
    expect(await screen.findByText('测试解释文字')).toBeInTheDocument();
  });

  it('支持自定义图标', () => {
    render(<TooltipIcon content="test"><span>❓</span></TooltipIcon>);
    expect(screen.getByText('❓')).toBeInTheDocument();
  });

  it('图标有 help 形状光标', () => {
    render(<TooltipIcon content="test" />);
    expect(screen.getByText('ⓘ')).toHaveStyle('cursor: help');
  });
});
