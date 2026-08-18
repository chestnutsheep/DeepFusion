import React, { useEffect, useRef, useState } from "react";

// ── 颜色 / 格式化（红涨绿跌，与项目约定一致） ──
export const UP = "#ef232a";
export const DOWN = "#14b143";
export const GREY = "#909399";

export const tone = (v) => (v > 0 ? UP : v < 0 ? DOWN : GREY);
export const fmtPct = (v) =>
  v == null || isNaN(v) ? "--" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
export const fmtYi = (v) =>
  v == null || isNaN(v) ? "--" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}亿`;
export const fmtMoneyYi = (v) =>
  v == null || isNaN(v) ? "--" : `${Number(v).toFixed(1)}亿`;

export function safeParse(raw) {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// 组件内卡片容器样式（Widget 内部内容块复用）
export const cardBox = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid var(--border-subtle)",
  borderRadius: "var(--radius)",
  padding: "var(--sp-sm) var(--sp-md)",
};

// ── 悬浮信息卡（锚定触发元素，离开即消失，不跟随鼠标） ──
export function InfoCard({ anchorRef, title, rows, placement = "right" }) {
  const style = {
    position: "fixed",
    zIndex: 9999,
    pointerEvents: "none",
    background: "rgba(20,30,30,0.96)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius)",
    padding: "10px 12px",
    width: 240,
    boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
    fontSize: 12,
    color: "var(--text-secondary)",
  };
  if (anchorRef && anchorRef.current) {
    const r = anchorRef.current.getBoundingClientRect();
    const W = 252, H = 160;
    let left = r.right + 10;
    let top = r.top;
    if (placement === "left") left = r.left - W - 10;
    if (placement === "bottom") {
      left = r.left;
      top = r.bottom + 10;
    }
    left = Math.max(8, Math.min(left, window.innerWidth - W - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - H - 8));
    style.left = left;
    style.top = top;
  }
  return (
    <div style={style}>
      <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>{title}</div>
      {rows.map((r, i) => (
        <div
          key={i}
          style={{ display: "flex", justifyContent: "space-between", lineHeight: 1.7 }}
        >
          <span style={{ color: "var(--text-muted)" }}>{r[0]}</span>
          <span style={{ color: r[2] || "var(--text-secondary)", fontWeight: 500 }}>{r[1]}</span>
        </div>
      ))}
    </div>
  );
}

export function useHoverCard() {
  // 返回 [state, open(anchorEl,title,rows), close]
  const [card, setCard] = useState(null); // {anchor,title,rows}
  const open = useCallback((anchor, title, rows) => {
    setCard({ anchor, title, rows });
  }, []);
  const close = useCallback(() => setCard(null), []);
  return [card, open, close];
}

// ── 卡片堆：平时收起，悬浮锚定元素后自适应方向弹出 ──
export function CollapsibleStack({
  title,
  count,
  icon = "📊",
  children,
  placement = "bottom",
  maxHeight = 320,
  accent,
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const popRef = useRef(null);

  // 计算弹出方向，避免溢出视口
  const computePos = () => {
    if (!wrapRef.current) return {};
    const r = wrapRef.current.getBoundingClientRect();
    const ph = Math.min(maxHeight, (children?.length || 0) * 56 + 60);
    const pw = Math.max(320, r.width);
    let left = r.left;
    let top = r.bottom + 8;
    let realPlacement = "bottom";
    if (placement === "auto" || placement === "bottom") {
      if (r.bottom + ph + 12 > window.innerHeight && r.top - ph - 12 > 0) {
        top = r.top - ph - 8;
        realPlacement = "top";
      }
    }
    if (placement === "right" || (placement === "auto" && realPlacement === "bottom" && r.right + pw + 12 > window.innerWidth && r.left - pw - 12 > 0)) {
      left = r.left - pw - 8;
      top = r.top;
      realPlacement = "left";
    }
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - ph - 8));
    return { left, top, pw, ph, realPlacement };
  };

  const [pos, setPos] = useState(null);
  const show = () => {
    setPos(computePos());
    setOpen(true);
  };
  const hide = () => {
    setOpen(false);
    setPos(null);
  };

  return (
    <>
      <div
        ref={wrapRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.05) 0%, var(--bg-panel) 100%)",
          border: `1.5px solid ${accent || "rgba(212,168,83,0.45)"}`,
          borderRadius: "var(--radius)",
          padding: "var(--sp-md)",
          cursor: "pointer",
          transition: "all var(--transition, 0.25s ease)",
          boxShadow: open
            ? "inset 0 1px 0 rgba(255,255,255,0.2), 0 0 28px rgba(212,168,83,0.25)"
            : "inset 0 1px 0 rgba(255,255,255,0.12), 0 6px 24px rgba(0,0,0,0.28)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22, lineHeight: 1 }}>{icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-primary)", fontWeight: 600 }}>
              {title}
            </div>
            <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", marginTop: 2 }}>
              {count != null ? `${count} 项 · ` : ""}悬浮展开
            </div>
          </div>
          <span style={{ fontSize: 12, color: accent || "var(--gold)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▾</span>
        </div>
      </div>

      {open && pos && (
        <div
          ref={popRef}
          style={{
            position: "fixed",
            left: pos.left,
            top: pos.top,
            width: pos.pw,
            maxHeight: pos.ph,
            overflowY: "auto",
            zIndex: 9998,
            background: "rgba(18,26,26,0.97)",
            border: `1px solid ${accent || "rgba(212,168,83,0.5)"}`,
            borderRadius: "var(--radius)",
            padding: "var(--sp-md)",
            boxShadow: "0 16px 48px rgba(0,0,0,0.55)",
            backdropFilter: "blur(8px)",
          }}
        >
          {children}
        </div>
      )}
    </>
  );
}

// ── 大盘指数卡片 ──
export function IndexCard({ it, onHover, onLeave }) {
  const pct = it.change_pct;
  const color = tone(pct);
  const ref = useRef(null);
  return (
    <div
      ref={ref}
      onMouseEnter={() =>
        onHover(ref.current, it.name, [
          ["最新价", it.price != null ? it.price.toFixed(2) : "--", color],
          ["涨跌额", fmtPct(it.change), tone(it.change)],
          ["涨跌幅", fmtPct(pct), color],
          ["成交额", it.amount != null ? `${fmtMoneyYi(it.amount / 1e8)}` : "--"],
          ["代码", it.code || "--"],
        ])
      }
      onMouseLeave={onLeave}
      style={{
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
        borderLeft: `3px solid ${color}`,
        borderRadius: "var(--radius)",
        padding: "10px 12px",
        cursor: "default",
      }}
    >
      <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 4 }}>{it.name}</div>
      <div className="df-num-lg" style={{ color }}>
        {it.price != null ? it.price.toFixed(2) : "--"}
      </div>
      <div style={{ fontSize: "var(--fs-xs)", color, marginTop: 2 }}>{fmtPct(pct)}</div>
    </div>
  );
}

// ── 板块涨跌小方块（hover 锚定信息卡，不跟随鼠标）──
export function SectorTile({ s, onHover, onLeave }) {
  const pct = s.change_pct;
  const color = tone(pct);
  const intensity = Math.min(Math.abs(pct || 0) / 3, 0.55);
  const bg = pct >= 0 ? `rgba(239,35,42,${intensity})` : `rgba(20,177,67,${intensity})`;
  const ref = useRef(null);
  return (
    <div
      ref={ref}
      onMouseEnter={() =>
        onHover(ref.current, s.name, [
          ["涨跌幅", fmtPct(pct), color],
          ["领涨股", s.leader || "—"],
        ])
      }
      onMouseLeave={onLeave}
      style={{
        background: bg,
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        padding: "8px 6px",
        textAlign: "center",
        cursor: "default",
      }}
    >
      <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {s.name}
      </div>
      <div style={{ fontSize: "var(--fs-xs)", fontWeight: 600, color }}>{fmtPct(pct)}</div>
    </div>
  );
}

// ── 资金面卡片（含环比）──
export function FlowCard({ title, data, valueLabel, note }) {
  if (!data) return null;
  if (data.error || data.available === false) {
    const isError = !!data.error;
    return (
      <div style={cardBox}>
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>{title}</div>
        <div style={{ fontSize: "var(--fs-xs)", color: isError ? "var(--accent-red)" : "var(--accent-gold)", marginTop: 6 }}>
          {isError ? "数据获取失败" : "数据暂不可用"}
        </div>
        {data.note && (
          <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginTop: 4 }}>{data.note}</div>
        )}
      </div>
    );
  }
  const v = data.value_yi != null ? data.value_yi : data.value;
  const d = data.delta_yi != null ? data.delta_yi : data.delta; // 优先亿单位
  const dp = data.delta_pct;
  const color = tone(v);
  return (
    <div style={cardBox}>
      <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 6 }}>{title}</div>
      <div className="df-num-lg" style={{ color, fontSize: "var(--fs-2xl)" }}>
        {v != null ? `${v.toFixed(1)}亿` : "--"}
      </div>
      {d != null && (
        <div style={{ fontSize: "var(--fs-xs)", color: tone(d), marginTop: 4 }}>
          环比 {fmtYi(d)}（{fmtPct(dp)}）
        </div>
      )}
      <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginTop: 4 }}>
        {data.date || "--"}
        {note ? ` · ${note}` : ""}
      </div>
    </div>
  );
}
