export const mcp = {
  async callWithMeta(toolName, args = {}) {
    const response = await fetch('/api/tools/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: toolName,
        arguments: args,
      }),
    });
    const json = await response.json();
    if (!json.ok) throw new Error(json.error || 'MCP call failed');
    return { data: json.data || null, updatedAt: json.updatedAt || null };
  },

  async call(toolName, args = {}) {
    const { data } = await this.callWithMeta(toolName, args);
    return data;
  },

  policy: {
    stats: () => mcp.call('policy_stats'),
    search: (keyword = '', org = '', limit = 50) =>
      mcp.call('policy_search', { keyword, org, limit }),
    timeline: (year) => mcp.call('policy_timeline', { year }),
    collect: () => mcp.call('policy_collect', { max_pages: 2 }),
  },

  cycles: {
    status: () => mcp.call('cycle_cache_status'),
  },
};
