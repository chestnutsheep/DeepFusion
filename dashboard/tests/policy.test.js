import { describe, it, expect } from 'vitest';

function extractKeywords(line) {
  const m = line.match(/\[(.+?)\]/);
  if (!m) return [];
  return m[1].split(',').map(s => s.trim()).filter(Boolean);
}

function extractUrl(line) {
  // 格式末尾的 URL
  const parts = line.trim().split(/\s+/);
  const last = parts[parts.length - 1];
  if (last && (last.startsWith('http://') || last.startsWith('https://'))) return last;
  return '';
}

function extractSummary(line) {
  const cleaned = line.replace(/^\s+/, '');
  const dateMatch = cleaned.match(/^\d{4}-\d{2}-\d{2}\s{2,}(.+?)(?:\s+\([^)]+\))?\s*\[/);
  if (dateMatch) return dateMatch[1].trim();
  return cleaned.substring(0, 50);
}

describe('policy text extraction', () => {
  it('提取关键词标签', () => {
    const line = '  2026-06-02   国务院关于印发《加快农业农村现代化"十五五"规划》的通知 (国务院) [十五五,五年规划,消费,改革,财政,绿色,投资,人工智能,新能源,创新,产业链]  https://www.gov.cn/test';
    const kw = extractKeywords(line);
    expect(kw).toContain('十五五');
    expect(kw).toContain('消费');
    expect(kw).toContain('新能源');
    expect(kw).toContain('人工智能');
    expect(kw.length).toBe(11);
  });

  it('提取 URL', () => {
    const line = '  2026-06-02   国务院通知  [十五五]  https://www.gov.cn/test';
    expect(extractUrl(line)).toBe('https://www.gov.cn/test');
  });

  it('无 URL 返回空', () => {
    expect(extractUrl('  2026-06-02   普通文件  [标签]')).toBe('');
  });

  it('无关键词标签返回空数组', () => {
    expect(extractKeywords('  2026-06-02   普通文件')).toEqual([]);
  });

  it('提取摘要', () => {
    const line = '  2026-06-02   国务院关于印发《加快农业农村现代化"十五五"规划》的通知 (国务院) [十五五,消费]  https://www.gov.cn';
    const summary = extractSummary(line);
    expect(summary).toContain('农业农村现代化');
    expect(summary).toContain('十五五');
  });
});

describe('PolicyDashboard 组件', () => {
  it('可以被 import', async () => {
    const mod = await import('../src/components/Policy/PolicyDashboard.jsx');
    expect(mod.default).toBeDefined();
  });
});
