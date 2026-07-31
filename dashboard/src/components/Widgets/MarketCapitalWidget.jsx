import React from "react";
import { FlowCard, cardBox, tone, fmtYi, fmtMoneyYi, UP } from "./marketShared";

export default function MarketCapitalWidget({ capitalData }) {
  if (!capitalData) {
    return <div style={{ color: "#8b949e", fontSize: 13 }}>暂无资金面数据</div>;
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
        gap: 12,
      }}
    >
      <FlowCard title="两融余额" data={capitalData.margin} />
      <FlowCard title="北向资金(净流入)" data={capitalData.north} />
      <FlowCard title="南向资金(净流入)" data={capitalData.south} />
      {capitalData.public_fund && !capitalData.public_fund.error ? (
        <div style={cardBox}>
          <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 6 }}>公募/ETF 资金偏好</div>
          <div style={{ fontSize: 12, color: "#8b949e" }}>净流入 Top3 行业</div>
          {(capitalData.public_fund.top_inflow || []).slice(0, 3).map((r, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, lineHeight: 1.8 }}>
              <span style={{ color: "#c9d1d9" }}>{r.name}</span>
              <span style={{ color: UP }}>{r.net_yi != null ? `${r.net_yi}亿` : "--"}</span>
            </div>
          ))}
          <div style={{ fontSize: 10, color: "#6e7681", marginTop: 4 }}>{capitalData.public_fund.note}</div>
        </div>
      ) : (
        <FlowCard title="公募/ETF" data={capitalData.public_fund} />
      )}
      {capitalData.nation_team && !capitalData.nation_team.error ? (
        <div style={cardBox}>
          <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 6 }}>国家队/主力(代理)</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: tone(capitalData.nation_team.total_net_yi) }}>
            {fmtYi(capitalData.nation_team.total_net_yi)}
          </div>
          <div style={{ fontSize: 10, color: "#6e7681", marginTop: 4 }}>{capitalData.nation_team.note}</div>
        </div>
      ) : (
        <FlowCard title="国家队" data={capitalData.nation_team} />
      )}
      {capitalData.social_security && (
        <div style={cardBox}>
          <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 6 }}>社保基金</div>
          <div style={{ fontSize: 11, color: "#d29922" }}>{capitalData.social_security.note}</div>
        </div>
      )}
    </div>
  );
}
