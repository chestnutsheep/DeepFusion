import React from "react";
import { SectorTile, CollapsibleStack } from "./marketShared";

export default function MarketSectorsWidget({ sectors = [], onHover, onLeave, stackable = false }) {
  if (!sectors.length) {
    return <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-xs)" }}>暂无板块数据</div>;
  }
  const grid = (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))",
        gap: "var(--sp-xs)",
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
  if (!stackable) return grid;
  return (
    <CollapsibleStack
      title="行业板块涨跌"
      count={sectors.length}
      icon="📈"
      accent="rgba(143,214,255,0.5)"
      maxHeight={360}
    >
      {grid}
    </CollapsibleStack>
  );
}
