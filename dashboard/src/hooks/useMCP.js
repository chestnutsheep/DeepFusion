import {useQuery} from '@tanstack/react-query';
import {mcp} from '../services/mcp.js';

/**
 * 按工具名返回合理的 staleTime（毫秒）。
 * - 搜索类：2 分钟（需要实时性）
 * - 政策类：30 分钟（爬虫不频繁更新）
 * - 宏观类：24 小时
 * - 其余：8 小时
 */
function getStaleTime(toolName) {
  if (!toolName) return 8 * 60 * 60 * 1000;
  if (toolName.startsWith('macro_')) return 24 * 60 * 60 * 1000;
  if (toolName.startsWith('policy_')) return 30 * 60 * 1000;
  if (toolName === 'search') return 2 * 60 * 1000;
  // 行业数据：5分钟刷新，确保盘中/收盘后数据及时更新
  if (toolName.startsWith('industry_')) return 5 * 60 * 1000;
  // 国际金融压力：5分钟（实时利差/汇率监测）
  if (toolName === 'financial_stress_index' || toolName === 'capital_flow_monitor') return 5 * 60 * 1000;
  // 国际债务/泡沫：30分钟（季度月频数据）
  if (toolName === 'debt_sustainability' || toolName === 'asset_bubble_watch') return 30 * 60 * 1000;
  return 8 * 60 * 60 * 1000;
}

/**
 * MCP 工具查询 hook。
 * @param {string} toolName
 * @param {object|null} args — 传 null 时禁用查询（避免无效请求）
 */
export function useMCP(toolName, args = {}) {
  const queryKey = [toolName, JSON.stringify(args)];
  const query = useQuery({
    queryKey,
    queryFn: () => mcp.callWithMeta(toolName, args),
    enabled: args !== null,
    staleTime: getStaleTime(toolName),
    retry: 1,
  });
  // 向后兼容：调用方期望 data 是字符串；额外暴露 updatedAt
  return {
    ...query,
    data: query.data?.data,
    updatedAt: query.data?.updatedAt,
  };
}