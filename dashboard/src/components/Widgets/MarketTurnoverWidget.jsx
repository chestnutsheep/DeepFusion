import React from "react";
import { cardBox, tone, fmtYi, fmtPct, fmtMoneyYi, GREY } from "./marketShared";

export default function MarketTurnoverWidget({ turnover }) {
  if (!turnover) {
    return <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-xs)" }}>暂无成交数据</div>;
  }
  return (
    <div style={{ ...cardBox, display: "flex", gap: 28, flexWrap: "wrap", alignItems: "center" }}>
      <div>
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>今日成交额(沪+深近似)</div>
        <div className="df-num-lg">{fmtMoneyYi(turnover.today_yi)}</div>
      </div>
      <div>
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>较上次快照</div>
        {turnover.delta_yi != null ? (
          <div style={{ fontSize: "var(--fs-2xl)", fontWeight: 700, color: tone(turnover.delta_yi) }}>
            {turnover.delta_yi >= 0 ? "▲" : "▼"} {fmtYi(Math.abs(turnover.delta_yi))}
            <span style={{ fontSize: "var(--fs-base)", marginLeft: 8 }}>（{fmtPct(turnover.delta_pct)}）</span>
          </div>
        ) : (
          <div style={{ fontSize: "var(--fs-2xl)", fontWeight: 700, color: "var(--text-muted)" }}>首次快照·暂无环比</div>
        )}
      </div>
      <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>
        {turnover.date} · {turnover.note || ""}
      </div>
    </div>
  );
}
