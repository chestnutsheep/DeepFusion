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
  QualityStockWidget,
} from "../components/Widgets/DailyWidgets.jsx";
import InvestThemeWidget from "../components/Reports/InvestThemeWidget.jsx";

export default function DailyBoardPage() {
  const scene = useMarketScene();
  const meta = SCENE_META[scene];
  const navigate = useNavigate();
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const lu = useMCP("limit_up_latest", {});
  const calib = useMCP("limit_up_calibration_latest", {});

  // 修复：进入每日看板时锁定侧栏到 daily，避免侧栏子导航误显其它模块面板
  useEffect(() => {
    if (activeTab !== "daily") setActiveTab("daily");
  }, [activeTab, setActiveTab]);

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

  return (
    <div>
      <div style={{ marginBottom: "var(--sp-lg)" }}>
        <h1 className="df-h1" style={{ margin: 0 }}>
          每日看板 · 决策工作台
        </h1>
        <p className="df-body" style={{ margin: "6px 0 0" }}>
          连板潜力股埋伏 + 金融大事日历提前布局 + 投资方向主题追踪 + 每日定时报告 + 优质股推送。左侧「配置圈」给出当日推荐资产组合，点击任一资产段可直达对应实战产品市场。
        </p>
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

      {/* ① 连板分析（潜质股评分 + 评分校准透明） */}
      <SectionHeader title="① 连板分析 · 潜质股埋伏" />
      <ErrorBoundary>
        <LimitUpWidget stocks={luStocks} />
      </ErrorBoundary>
      <div style={{ marginTop: "var(--sp-md)" }}>
        <CalibrationWidget data={calibData} />
      </div>

      {/* ② 金融大事日历（固定张数 + 翻页） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="② 金融大事日历 · 事件卡片" />
        <ErrorBoundary>
          <CalendarWidget pageSize={6} paged />
        </ErrorBoundary>
      </div>

      {/* ③ 7×24 财经快讯 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="③ 7×24 财经快讯" />
        <ErrorBoundary>
          <NewsWidget />
        </ErrorBoundary>
      </div>

      {/* ④ 投资方向 · 主题追踪 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="④ 投资方向 · 主题追踪" />
        <ErrorBoundary>
          <InvestThemeWidget />
        </ErrorBoundary>
      </div>

      {/* ⑤ 每日报告（盘前 / 午间 / 每日复盘） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="⑤ 每日报告 · 盘前 / 午间 / 复盘" />
        <ErrorBoundary>
          <ReportsWidget reloadToken={reloadToken} />
        </ErrorBoundary>
      </div>

      {/* ⑥ 优质股推送（含 5 日胜率回测 + 反思） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="⑥ 优质股推送 · 回测追踪" />
        <ErrorBoundary>
          <QualityStockWidget />
        </ErrorBoundary>
      </div>
    </div>
  );
}
