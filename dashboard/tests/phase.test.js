import { describe, it, expect } from 'vitest';
import { getPhaseName, getPhaseSignal, resolveCyclePhase } from './helpers';

describe('phase_utils', () => {
  it('getPhaseName 映射正确', () => {
    expect(getPhaseName(1)).toBe('复苏');
    expect(getPhaseName(2)).toBe('繁荣');
    expect(getPhaseName(3)).toBe('衰退');
    expect(getPhaseName(4)).toBe('萧条');
  });

  it('getPhaseName 支持 kond 类型', () => {
    expect(getPhaseName(1, 'kond')).toBe('回升期');
    expect(getPhaseName(2, 'kond')).toBe('繁荣期');
    expect(getPhaseName(3, 'kond')).toBe('衰退期');
    expect(getPhaseName(4, 'kond')).toBe('萧条期');
  });

  it('getPhaseSignal 返回正负信号', () => {
    expect(getPhaseSignal(1)).toBe(1.0);
    expect(getPhaseSignal(2)).toBe(2.0);
    expect(getPhaseSignal(3)).toBe(-1.0);
    expect(getPhaseSignal(4)).toBe(-2.0);
    expect(getPhaseSignal(0)).toBe(0.0);
  });

  it('resolveCyclePhase 解析 kitchin 行', () => {
    const row = { stage: 3, stage_name: '主动补库存', demand_yoy: 5.0 };
    const result = resolveCyclePhase(row, 'kitchin');
    expect(result.cycle_phase).toBe(3);
    expect(result.cycle_phase_name).toBe('主动补库存');
    expect(result.cycle_signal).toBe(-1.0);
  });

  it('resolveCyclePhase 解析 macro 行', () => {
    const row = { phase: 1, phase_name: '复苏', value: 10 };
    const result = resolveCyclePhase(row, 'macro');
    expect(result.cycle_phase).toBe(1);
    expect(result.cycle_phase_name).toBe('复苏');
    expect(result.cycle_signal).toBe(1.0);
  });

  it('resolveCyclePhase 无相位字段返回原行', () => {
    const row = { value: 10 };
    const result = resolveCyclePhase(row);
    expect(result.value).toBe(10);
    expect(result.cycle_phase).toBeUndefined();
  });
});
