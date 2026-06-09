import { describe, it, expect, beforeEach } from 'vitest';
import { mcp } from '../src/services/mcp';

describe('mcp.call', () => {
  beforeEach(() => {
    global.fetch = undefined;
  });

  it('成功返回数据文本', async () => {
    global.fetch = async () => ({
      json: async () => ({ ok: true, data: '{"gdp":6.7}' }),
    });
    const result = await mcp.call('macro_gdp');
    expect(result).toBe('{"gdp":6.7}');
  });

  it('API 返回 error 时抛异常', async () => {
    global.fetch = async () => ({
      json: async () => ({ ok: false, error: '工具不存在' }),
    });
    await expect(mcp.call('__nonexistent__')).rejects.toThrow('工具不存在');
  });

  it('data 为 null 时返回 null', async () => {
    global.fetch = async () => ({
      json: async () => ({ ok: true, data: null }),
    });
    const result = await mcp.call('some_tool');
    expect(result).toBeNull();
  });

  it('发送正确的请求格式', async () => {
    let bodySent;
    global.fetch = async (url, opts) => {
      bodySent = JSON.parse(opts.body);
      return { json: async () => ({ ok: true, data: 'ok' }) };
    };
    await mcp.call('data_kitchin', { limit: 10 });
    expect(bodySent.name).toBe('data_kitchin');
    expect(bodySent.arguments.limit).toBe(10);
  });

  it('无 args 时传空对象', async () => {
    let argsSent;
    global.fetch = async (url, opts) => {
      argsSent = JSON.parse(opts.body).arguments;
      return { json: async () => ({ ok: true, data: 'ok' }) };
    };
    await mcp.call('get_current_time');
    expect(argsSent).toEqual({});
  });

  it('网络请求失败时抛出 fetch 异常', async () => {
    global.fetch = async () => { throw new Error('Network error'); };
    await expect(mcp.call('any_tool')).rejects.toThrow('Network error');
  });
});

describe('mcp.policy', () => {
  beforeEach(() => {
    global.fetch = undefined;
  });

  it('stats 调用 policy_stats', async () => {
    global.fetch = async (url, opts) => {
      const body = JSON.parse(opts.body);
      expect(body.name).toBe('policy_stats');
      return { json: async () => ({ ok: true, data: '政策文件库: 共 31 篇' }) };
    };
    const result = await mcp.policy.stats();
    expect(result).toContain('31');
  });

  it('search 调用 policy_search 传参', async () => {
    let argsSent;
    global.fetch = async (url, opts) => {
      argsSent = JSON.parse(opts.body).arguments;
      return { json: async () => ({ ok: true, data: '共 5 条\n  2026-06-02   国务院通知' }) };
    };
    const result = await mcp.policy.search('十五五', '国务院', 3);
    expect(argsSent.keyword).toBe('十五五');
    expect(argsSent.org).toBe('国务院');
    expect(argsSent.limit).toBe(3);
    expect(result).toContain('5 条');
  });

  it('search 默认参数', async () => {
    let argsSent;
    global.fetch = async (url, opts) => {
      argsSent = JSON.parse(opts.body).arguments;
      return { json: async () => ({ ok: true, data: '' }) };
    };
    await mcp.policy.search();
    expect(argsSent.keyword).toBe('');
    expect(argsSent.org).toBe('');
    expect(argsSent.limit).toBe(50);
  });
});

describe('mcp.cycles', () => {
  beforeEach(() => {
    global.fetch = undefined;
  });

  it('status 调用 cycle_cache_status', async () => {
    global.fetch = async () => ({
      json: async () => ({ ok: true, data: '{"kitchin": true}' }),
    });
    const result = await mcp.cycles.status();
    expect(result).toContain('kitchin');
  });
});
