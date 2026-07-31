import { useState, useEffect, useCallback } from "react";

const DEFAULT_STORAGE_KEY = "df_board_layout_v1";

// 看板布局本地持久化：顺序 + 每个 widget 的自定义标题/标签
// 与后端无关，纯前端 localStorage，保证刷新后保持用户编排。
export function useBoardLayout(defaultOrder, storageKey = DEFAULT_STORAGE_KEY) {
  const [layout, setLayout] = useState(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        const order = parsed.order || [];
        // 合并：保留存储顺序中仍存在的 id；新增的默认 id 追加到末尾
        const existing = order.filter((id) => defaultOrder.includes(id));
        const fresh = defaultOrder.filter((id) => !order.includes(id));
        return { order: [...existing, ...fresh], meta: parsed.meta || {} };
      }
    } catch {
      /* ignore */
    }
    return { order: [...defaultOrder], meta: {} };
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(layout));
    } catch {
      /* ignore */
    }
  }, [layout]);

  const reorder = useCallback((fromId, toId) => {
    setLayout((prev) => {
      const order = [...prev.order];
      const from = order.indexOf(fromId);
      const to = order.indexOf(toId);
      if (from === -1 || to === -1 || from === to) return prev;
      order.splice(from, 1);
      order.splice(to, 0, fromId);
      return { ...prev, order };
    });
  }, []);

  const updateMeta = useCallback((id, patch) => {
    setLayout((prev) => ({
      ...prev,
      meta: { ...prev.meta, [id]: { ...(prev.meta[id] || {}), ...patch } },
    }));
  }, []);

  const resetLayout = useCallback(() => {
    setLayout({ order: [...defaultOrder], meta: {} });
  }, [defaultOrder]);

  return { order: layout.order, meta: layout.meta, reorder, updateMeta, resetLayout };
}
