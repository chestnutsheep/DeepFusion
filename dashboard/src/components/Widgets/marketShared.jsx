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
  border: "1px solid #2d3340",
  borderRadius: 8,
  padding: "12px 14px",
};

// ── 悬浮信息卡 ──
export function InfoCard({ x, y, title, rows }) {
  const style = {
    position: "fixed",
    left: Math.min(x + 14, window.innerWidth - 260),
    top: Math.min(y + 14, window.innerHeight - 160),
    zIndex: 9999,
    pointerEvents: "none",
    background: "rgba(20,24,33,0.96)",
    border: "1px solid #2d3340",
    borderRadius: 8,
    padding: "10px 12px",
    width: 240,
    boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
    fontSize: 12,
    color: "#c9d1d9",
  };
  return (
    <div style={style}>
      <div style={{ fontWeight: 600, color: "#fff", marginBottom: 6 }}>{title}</div>
      {rows.map((r, i) => (
        <div
          key={i}
          style={{ display: "flex", justifyContent: "space-between", lineHeight: 1.7 }}
        >
          <span style={{ color: "#8b949e" }}>{r[0]}</span>
          <span style={{ color: r[2] || "#c9d1d9", fontWeight: 500 }}>{r[1]}</span>
        </div>
      ))}
    </div>
  );
}

export function useHoverCard() {
  const [card, setCard] = useState(null); // {x,y,title,rows}
  const cardRef = useRef(null);
  cardRef.current = card;
  useEffect(() => {
    const onMove = (e) => {
      if (cardRef.current) {
        setCard({ ...cardRef.current, x: e.clientX, y: e.clientY });
      }
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);
  return [card, setCard];
}

// ── 大盘指数卡片 ──
export function IndexCard({ it, onHover, onLeave }) {
  const pct = it.change_pct;
  const color = tone(pct);
  return (
    <div
      onMouseEnter={(e) =>
        onHover(e, it.name, [
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
        borderRadius: 8,
        padding: "10px 12px",
        cursor: "default",
      }}
    >
      <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 4 }}>{it.name}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color }}>
        {it.price != null ? it.price.toFixed(2) : "--"}
      </div>
      <div style={{ fontSize: 12, color, marginTop: 2 }}>{fmtPct(pct)}</div>
    </div>
  );
}

// ── 板块涨跌小方块 ──
export function SectorTile({ s, onHover, onLeave }) {
  const pct = s.change_pct;
  const color = tone(pct);
  const intensity = Math.min(Math.abs(pct || 0) / 3, 0.55);
  const bg = pct >= 0 ? `rgba(239,35,42,${intensity})` : `rgba(20,177,67,${intensity})`;
  return (
    <div
      onMouseEnter={(e) =>
        onHover(e, s.name, [
          ["涨跌幅", fmtPct(pct), color],
          ["领涨股", s.leader || "—"],
        ])
      }
      onMouseLeave={onLeave}
      style={{
        background: bg,
        border: "1px solid #2d3340",
        borderRadius: 6,
        padding: "8px 6px",
        textAlign: "center",
        cursor: "default",
      }}
    >
      <div style={{ fontSize: 12, color: "#e6edf3", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {s.name}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color }}>{fmtPct(pct)}</div>
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
        <div style={{ fontSize: 13, color: "#c9d1d9" }}>{title}</div>
        <div style={{ fontSize: 12, color: isError ? "#f85149" : "#d29922", marginTop: 6 }}>
          {isError ? "数据获取失败" : "数据暂不可用"}
        </div>
        {data.note && (
          <div style={{ fontSize: 10, color: "#6e7681", marginTop: 4 }}>{data.note}</div>
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
      <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>
        {v != null ? `${v.toFixed(1)}亿` : "--"}
      </div>
      {d != null && (
        <div style={{ fontSize: 12, color: tone(d), marginTop: 4 }}>
          环比 {fmtYi(d)}（{fmtPct(dp)}）
        </div>
      )}
      <div style={{ fontSize: 11, color: "#8b949e", marginTop: 4 }}>
        {data.date || "--"}
        {note ? ` · ${note}` : ""}
      </div>
    </div>
  );
}
