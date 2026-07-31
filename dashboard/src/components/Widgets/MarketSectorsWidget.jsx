import React from "react";
import { SectorTile } from "./marketShared";

export default function MarketSectorsWidget({ sectors = [], onHover, onLeave }) {
  if (!sectors.length) {
    return <div style={{ color: "#8b949e", fontSize: 13 }}>暂无板块数据</div>;
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))",
        gap: 8,
      }}
    >
      {sectors.map((s, i) => (
        <SectorTile
          key={i}
          s={s}
          onHover={(e, t, r) => onHover(e, t, r)}
          onLeave={onLeave}
        />
      ))}
    </div>
  );
}
