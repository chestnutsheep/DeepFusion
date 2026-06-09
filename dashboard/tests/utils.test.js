import { describe, it, expect } from 'vitest';
import {
  getDirection,
  getArrow,
  getColor,
  formatValue,
  prepareGridItems,
} from './helpers';

// ─── getDirection ─────────────────────────────────────
describe('getDirection', () => {
  it('值上升返回 up', () => expect(getDirection(6.7, 5.2)).toBe('up'));
  it('值下降返回 down', () => expect(getDirection(4.0, 5.0)).toBe('down'));
  it('值相等返回 null', () => expect(getDirection(5.0, 5.0)).toBeNull());
  it('value 为 null 返回 null', () => expect(getDirection(null, 5.0)).toBeNull());
  it('prevValue 为 null 返回 null', () => expect(getDirection(5.0, null)).toBeNull());
  it('两个都为 null 返回 null', () => expect(getDirection(null, null)).toBeNull());
  it('负数上升', () => expect(getDirection(-3, -5)).toBe('up'));
  it('负数下降', () => expect(getDirection(-5, -3)).toBe('down'));
  it('从负数到正数', () => expect(getDirection(1, -5)).toBe('up'));
  it('从正数到负数', () => expect(getDirection(-1, 5)).toBe('down'));
});

// ─── getArrow ─────────────────────────────────────────
describe('getArrow', () => {
  it('up 返回 ↑', () => expect(getArrow('up')).toBe('↑'));
  it('down 返回 ↓', () => expect(getArrow('down')).toBe('↓'));
  it('null 返回空', () => expect(getArrow(null)).toBe(''));
  it('空字符串返回空', () => expect(getArrow('')).toBe(''));
});

// ─── getColor ─────────────────────────────────────────
describe('getColor', () => {
  describe('higherBetter=true', () => {
    it('up → 绿色', () => expect(getColor('up', true)).toBe('#3fb950'));
    it('down → 红色', () => expect(getColor('down', true)).toBe('#f85149'));
    it('null → 默认色', () => expect(getColor(null, true)).toBe('var(--text-primary)'));
  });
  describe('higherBetter=false', () => {
    it('up → 红色', () => expect(getColor('up', false)).toBe('#f85149'));
    it('down → 绿色', () => expect(getColor('down', false)).toBe('#3fb950'));
    it('null → 默认色', () => expect(getColor(null, false)).toBe('var(--text-primary)'));
  });
  describe('higherBetter=null', () => {
    it('有 direction → 金色', () => expect(getColor('up', null)).toBe('var(--accent-gold)'));
    it('无 direction → 金色', () => expect(getColor(null, null)).toBe('var(--accent-gold)'));
  });
  describe('higherBetter=undefined', () => {
    it('有 direction → 金色', () => expect(getColor('up')).toBe('var(--accent-gold)'));
    it('无 direction → text-primary', () => expect(getColor(null)).toBe('var(--text-primary)'));
  });
});

// ─── formatValue ──────────────────────────────────────
describe('formatValue', () => {
  it('数值保留指定小数', () => expect(formatValue(6.666, 1)).toBe('6.7'));
  it('整数加 .0', () => expect(formatValue(5, 1)).toBe('5.0'));
  it('三位小数保留两位', () => expect(formatValue(3.1415, 2)).toBe('3.14'));
  it('null 显示 —', () => expect(formatValue(null)).toBe('—'));
  it('undefined 显示 —', () => expect(formatValue(undefined)).toBe('—'));
  it('字符串原样返回', () => expect(formatValue('复苏')).toBe('复苏'));
  it('0 正确处理', () => expect(formatValue(0, 1)).toBe('0.0'));
  it('负数格式化', () => expect(formatValue(-1.5, 1)).toBe('-1.5'));
  it('默认 decimals=1', () => expect(formatValue(7)).toBe('7.0'));
});

// ─── prepareGridItems ─────────────────────────────────
describe('prepareGridItems', () => {
  const config = [
    { key: 'a', label: '指标A' },
    { key: 'b', label: '指标B', transform: v => v * 100 },
    { key: 'c', label: '指标C' },
  ];

  it('从数据中提取值', () => {
    const items = prepareGridItems(config, { a: 1, b: 0.5, c: 3 }, { a: 0, b: 0.2, c: 2 });
    expect(items).toHaveLength(3);
    expect(items[0].value).toBe(1);
    expect(items[0].prevValue).toBe(0);
  });

  it('应用 transform 函数', () => {
    const items = prepareGridItems(config, { a: 1, b: 0.5, c: 3 }, {});
    expect(items[0].value).toBe(1); // 无 transform
    expect(items[1].value).toBe(50); // 0.5 * 100
  });

  it('data 为 null 返回空数组', () => {
    expect(prepareGridItems(config, null, {})).toEqual([]);
  });

  it('缺失字段 value 为 undefined', () => {
    const items = prepareGridItems(config, { a: 1 }, {});
    expect(items[0].value).toBe(1);
    expect(items[1].value).toBeUndefined();
    expect(items[2].value).toBeUndefined();
  });

  it('prevData 为 null 时 prevValue 为 undefined', () => {
    const items = prepareGridItems(config, { a: 1 }, null);
    expect(items[0].prevValue).toBeUndefined();
  });

  it('transform 不处理 null', () => {
    const items = prepareGridItems(config, { a: 1, b: null, c: 3 }, {});
    expect(items[1].value).toBeNull();
  });
});
