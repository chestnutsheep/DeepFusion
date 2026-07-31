import React from "react";
import { cardBox, tone, fmtYi, fmtPct, fmtMoneyYi, GREY } from "./marketShared";

export default function MarketTurnoverWidget({ turnover }) {
  if (!turnover) {
    return <div style={{ color: "#8b949e", fontSize: 13 }}>暂无成交数据</div>;
  }
  return (
    <div style={{ ...cardBox, display: "flex", gap: 28, flexWrap: "wrap", alignItems: "center" }}>
      <div>
        <div style={{ fontSize: 12, color: "#8b949e" }}>今日成交额(沪+深近似)</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#e6edf3" }}>
          {fmtMoneyYi(turnover.today_yi)}
        </div>
      </div>
      <div>
        <div style={{ fontSize: 12, color: "#8b949e" }}>较上次快照</div>
        {turnover.delta_yi != null ? (
          <div style={{ fontSize: 22, fontWeight: 700, color: tone(turnover.delta_yi) }}>
            {turnover.delta_yi >= 0 ? "▲" : "▼"} {fmtYi(Math.abs(turnover.delta_yi))}
            <span style={{ fontSize: 14, marginLeft: 8 }}>（{fmtPct(turnover.delta_pct)}）</span>
          </div>
        ) : (
          <div style={{ fontSize: 22, fontWeight: 700, color: GREY }}>首次快照·暂无环比</div>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#8b949e" }}>
        {turnover.date} · {turnover.note || ""}
      </div>
    </div>
  );
}
