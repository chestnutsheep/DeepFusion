import React, { useRef } from "react";
import Widget from "./Widget";
import { useBoardLayout } from "./useBoardLayout";

// 可拖拽看板容器：管理顺序 + 拖拽重排 + 标签/标题自定义（持久化到 localStorage）
// widgets: [{ id, defaultTitle, colSpan, node }]
export default function WidgetBoard({ widgets, headerExtra, title = "我的看板", storageKey }) {
  const defaultOrder = widgets.map((w) => w.id);
  const { order, meta, reorder, updateMeta, resetLayout } = useBoardLayout(defaultOrder, storageKey);
  const dragId = useRef(null);

  // 按持久化顺序渲染；widgets 中缺失的项兜底保留
  const ordered = order
    .map((id) => widgets.find((w) => w.id === id))
    .filter(Boolean);

  return (
    <div>
      {/* 看板工具条 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 14,
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, color: "#e6edf3" }}>{title}</div>
        <span style={{ fontSize: 12, color: "#6e7681" }}>拖动 ⠿ 排序 · 双击标题重命名 · + 标签自定义</span>
        <button
          onClick={resetLayout}
          title="恢复默认布局"
          style={{
            marginLeft: "auto",
            background: "transparent",
            border: "1px solid #2d3340",
            color: "#8b949e",
            borderRadius: 6,
            fontSize: 12,
            padding: "4px 10px",
            cursor: "pointer",
          }}
        >
          重置布局
        </button>
      </div>

      {headerExtra}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
          gap: 14,
          alignItems: "start",
        }}
      >
        {ordered.map((w) => {
          const m = meta[w.id] || {};
          return (
            <Widget
              key={w.id}
              id={w.id}
              title={m.title || w.defaultTitle}
              defaultTitle={w.defaultTitle}
              tags={m.tags || []}
              colSpan={w.colSpan}
              onDragStartWidget={(id) => {
                dragId.current = id;
              }}
              onDragEnterWidget={(id) => {
                if (dragId.current && dragId.current !== id) {
                  reorder(dragId.current, id);
                  dragId.current = id;
                }
              }}
              onDragEndWidget={() => {
                dragId.current = null;
              }}
              onUpdateMeta={updateMeta}
            >
              {w.node}
            </Widget>
          );
        })}
      </div>
    </div>
  );
}
