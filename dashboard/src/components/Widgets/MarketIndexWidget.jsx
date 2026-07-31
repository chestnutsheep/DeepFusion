import React from "react";
import { IndexCard } from "./marketShared";

export default function MarketIndexWidget({ indices = [], onHover, onLeave }) {
  if (!indices.length) {
    return <div style={{ color: "#8b949e", fontSize: 13 }}>暂无指数数据</div>;
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
        gap: 10,
      }}
    >
      {indices.map((it, i) => (
        <IndexCard
          key={i}
          it={it}
          onHover={(e, t, r) => onHover(e, t, r)}
          onLeave={onLeave}
        />
      ))}
    </div>
  );
}
