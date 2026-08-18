import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMCP } from "../hooks/useMCP.js";
import ErrorBoundary from "../components/common/ErrorBoundary.jsx";
import SectionHeader from "../components/common/SectionHeader.jsx";
import UpdateTimestamp from "../components/common/UpdateTimestamp.jsx";
import { safeParse } from "../components/Widgets/marketShared.jsx";
import { useAppStore, useMarketScene, SCENE_META } from "../store/index.js";
import {
  LimitUpWidget,
  CalibrationWidget,
  ReportsWidget,
  CalendarWidget,
  NewsWidget,
} from "../components/Widgets/DailyWidgets.jsx";
import InvestThemeWidget from "../components/Reports/InvestThemeWidget.jsx";

// 顶部场景切换小卡：与宏观/中观/微观/政策/国际模块同步
const SCENE_CARDS = [
  { key: "daily", label: "概览", theme: "reve", path: "/", icon: "🗂" },
  { key: "macro", label: "宏观", theme: "matin", path: "/macro", icon: "🌐" },
  { key: "meso", label: "中观", theme: "crepuscule", path: "/meso", icon: "🏭" },
  { key: "micro", label: "微观", theme: "eclat", path: "/micro", icon: "🔬" },
  { key: "policy", label: "政策", theme: "reve", path: "/policy", icon: "📜" },
  { key: "global", label: "国际", theme: "lumiere", path: "/global", icon: "🌍" },
];

export default function DailyBoardPage() {
  const scene = useMarketScene();
  const meta = SCENE_META[scene];
  const navigate = useNavigate();
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setStoreTheme = useAppStore((s) => s.setTheme);
  const lu = useMCP("limit_up_latest", {});
  const calib = useMCP("limit_up_calibration_latest", {});

  const luData = useMemo(() => safeParse(lu.data), [lu.data]);
  const calibData = useMemo(() => safeParse(calib.data), [calib.data]);
  const luStocks = luData?.stocks || [];

  const [reloadToken, setReloadToken] = useState(0);

  const refreshAll = () => {
    lu.refetch?.();
    calib.refetch?.();
    setReloadToken((t) => t + 1);
  };

  const isFetching = lu.isFetching || calib.isFetching;
  // 备抵场景(收盘后/非交易日)：实时刷新无意义，禁用并提示
  const liveAllowed = scene === "live";

  const goScene = (sc) => {
    setActiveTab(sc.key);
    setStoreTheme(sc.theme);
    navigate(sc.path);
  };

  return (
    <div>
      <div style={{ marginBottom: "var(--sp-lg)" }}>
        <h1 className="df-h1" style={{ margin: 0 }}>
          每日看板 · 埋伏提示
        </h1>
        <p className="df-body" style={{ margin: "6px 0 0" }}>
          连板潜力股量化评分 + 金融大事日历提前埋伏 + 每日定时报告。可拖拽 / 自定义看板请在「微观 · 待机速览」中编排。
        </p>
      </div>

      {/* 场景切换小卡：与各大模块同步 */}
      <div style={{ display: "flex", gap: "var(--sp-sm)", marginBottom: 18, flexWrap: "wrap" }}>
        {SCENE_CARDS.map((sc) => {
          const active = activeTab === sc.key;
          return (
            <button
              key={sc.key}
              onClick={() => goScene(sc)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "10px 16px", borderRadius: "var(--radius)",
                cursor: "pointer", transition: "all 0.2s ease",
                background: active ? "rgba(212,168,83,0.18)" : "rgba(255,255,255,0.04)",
                border: active ? "1.5px solid rgba(212,168,83,0.6)" : "1.5px solid var(--border-subtle)",
                color: active ? "var(--accent-gold)" : "var(--text-secondary)",
                fontSize: "var(--fs-sm)", fontWeight: active ? 700 : 600,
                boxShadow: active ? "0 0 22px rgba(212,168,83,0.22)" : "none",
              }}
            >
              <span style={{ fontSize: 16 }}>{sc.icon}</span>
              {sc.label}
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <button
          className="btn-primary"
          onClick={refreshAll}
          disabled={isFetching || !liveAllowed}
          title={liveAllowed ? "拉取实时数据" : "非交易时段，展示最近交易日缓存快照"}
        >
          {isFetching ? "刷新中…" : liveAllowed ? "立即刷新" : "实时刷新(交易时段可用)"}
        </button>
        <span
          className="df-caption"
          style={{
            padding: "2px 10px", borderRadius: 999, fontWeight: 600,
            color: "#0b0f0a", background: meta.color,
          }}
        >
          {meta.label}
        </span>
        <span className="df-caption">
          <UpdateTimestamp dataTime={luData?.created_at} updatedAt={lu.updatedAt} />
        </span>
      </div>

      {/* 连板潜力股埋伏 */}
      <SectionHeader title="连板潜力股埋伏" />
      <ErrorBoundary>
        <LimitUpWidget stocks={luStocks} />
      </ErrorBoundary>

      {/* 连板评分校准 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="连板评分 · 校准透明" />
        <ErrorBoundary>
          <CalibrationWidget data={calibData} />
        </ErrorBoundary>
      </div>

      {/* 金融大事日历 + 热点/投资方向 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="金融大事日历 · 月历 / 甘特" />
        <ErrorBoundary>
          <CalendarWidget />
        </ErrorBoundary>
      </div>

      {/* 热点 / 投资方向（关键词触发采集 + 次日回测） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="热点 / 投资方向 · 主题追踪" />
        <ErrorBoundary>
          <InvestThemeWidget />
        </ErrorBoundary>
      </div>

      {/* 7×24 财经快讯（卡片堆收起，悬浮展开） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="7×24 财经快讯" />
        <ErrorBoundary>
          <NewsWidget />
        </ErrorBoundary>
      </div>

      {/* 每日报告 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="每日报告" />
        <ErrorBoundary>
          <ReportsWidget reloadToken={reloadToken} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
