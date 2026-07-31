import React, { useRef, useState } from "react";

// 通用看板卡片外壳：拖动手柄 + 可编辑标题 + 自定义标签（持久化到 layout）
// 仅当鼠标从手柄按下时才允许拖拽，避免干扰卡片内部交互（日历点击、链接、输入框）。
export default function Widget({
  id,
  title,
  defaultTitle,
  tags = [],
  colSpan = 1,
  onDragStartWidget,
  onDragEnterWidget,
  onDragEndWidget,
  onUpdateMeta,
  children,
}) {
  const allowDrag = useRef(false);
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const [tagDraft, setTagDraft] = useState("");
  const [dragging, setDragging] = useState(false);

  const commitTitle = () => {
    setEditing(false);
    const v = titleDraft.trim();
    onUpdateMeta?.(id, { title: v || undefined });
  };

  const addTag = () => {
    const v = tagDraft.trim();
    if (v && !tags.includes(v)) {
      onUpdateMeta?.(id, { tags: [...tags, v] });
    }
    setTagDraft("");
    setAdding(false);
  };

  const removeTag = (t) => {
    onUpdateMeta?.(id, { tags: tags.filter((x) => x !== t) });
  };

  return (
    <div
      draggable
      onDragStart={(e) => {
        if (!allowDrag.current) {
          e.preventDefault();
          return;
        }
        setDragging(true);
        onDragStartWidget?.(id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragEnd={() => {
        setDragging(false);
        allowDrag.current = false;
        onDragEndWidget?.();
      }}
      onDragEnter={() => {
        if (allowDrag.current) onDragEnterWidget?.(id);
      }}
      onDragOver={(e) => e.preventDefault()}
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid #2d3340",
        borderRadius: 12,
        padding: 14,
        opacity: dragging ? 0.5 : 1,
        boxShadow: dragging ? "0 0 0 2px #58a6ff66" : "none",
        transition: "opacity .12s",
        gridColumn: colSpan === "full" ? "1 / -1" : `span ${colSpan}`,
        minWidth: 0,
      }}
    >
      {/* 头部：手柄 + 标题 + 标签操作 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span
          onMouseDown={() => {
            allowDrag.current = true;
          }}
          onMouseUp={() => {
            allowDrag.current = false;
          }}
          title="拖动排序"
          style={{
            cursor: "grab",
            color: "#6e7681",
            fontSize: 16,
            lineHeight: 1,
            userSelect: "none",
          }}
        >
          ⠿
        </span>
        {editing ? (
          <input
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitTitle();
              if (e.key === "Escape") setEditing(false);
            }}
            placeholder={defaultTitle}
            style={{
              flex: 1,
              background: "rgba(0,0,0,0.3)",
              border: "1px solid #58a6ff",
              borderRadius: 6,
              color: "#e6edf3",
              fontSize: 15,
              fontWeight: 600,
              padding: "2px 8px",
            }}
          />
        ) : (
          <div
            onDoubleClick={() => {
              setTitleDraft(title || "");
              setEditing(true);
            }}
            title="双击重命名"
            style={{ flex: 1, fontSize: 15, fontWeight: 600, color: "#e6edf3", cursor: "text" }}
          >
            {title}
          </div>
        )}
        <button
          onClick={() => {
            setAdding((a) => !a);
            setTagDraft("");
          }}
          title="添加标签"
          style={{
            background: "transparent",
            border: "1px solid #2d3340",
            color: "#8b949e",
            borderRadius: 6,
            fontSize: 12,
            padding: "2px 8px",
            cursor: "pointer",
          }}
        >
          + 标签
        </button>
      </div>

      {/* 标签行 */}
      {(tags.length > 0 || adding) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10, alignItems: "center" }}>
          {tags.map((t, i) => (
            <span
              key={i}
              style={{
                background: "rgba(88,166,255,0.12)",
                border: "1px solid #58a6ff55",
                color: "#9ecbff",
                borderRadius: 999,
                fontSize: 11,
                padding: "2px 8px",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {t}
              <span
                onClick={() => removeTag(t)}
                style={{ cursor: "pointer", color: "#9ecbff", fontWeight: 700 }}
                title="删除标签"
              >
                ×
              </span>
            </span>
          ))}
          {adding && (
            <input
              autoFocus
              value={tagDraft}
              onChange={(e) => setTagDraft(e.target.value)}
              onBlur={addTag}
              onKeyDown={(e) => {
                if (e.key === "Enter") addTag();
                if (e.key === "Escape") setAdding(false);
              }}
              placeholder="输入标签回车"
              style={{
                background: "rgba(0,0,0,0.3)",
                border: "1px solid #58a6ff",
                borderRadius: 999,
                color: "#e6edf3",
                fontSize: 11,
                padding: "2px 8px",
                width: 100,
              }}
            />
          )}
        </div>
      )}

      {/* 内容 */}
      <div>{children}</div>
    </div>
  );
}
