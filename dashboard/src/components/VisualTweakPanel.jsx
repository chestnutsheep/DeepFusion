import React, { useEffect, useRef, useState } from "react";

// 浮动「视觉微调面板」—— 把仪表盘整体缩放 / 字号 / 间距做成可拖滑块，
// 实时写入 document.documentElement 的 zoom + --font-scale + --space-scale，
// 并存 localStorage，刷新后保持。相当于给你的看板一个「浏览器缩放 + 细节微调」把手。
const STORAGE_KEY = "df_visual_tweak_v1";
const DEFAULTS = { zoom: 1, fontScale: 1, spaceScale: 1 };

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch (e) {
    /* ignore */
  }
  return { ...DEFAULTS };
}

function applyToDom({ zoom, fontScale, spaceScale }) {
  const el = document.documentElement;
  // 全局统一缩放（类浏览器缩放，整体放大/缩小，比例不变）
  el.style.zoom = zoom;
  // 字号 / 间距独立倍率（仅影响使用 --fs-* / --sp-* token 的样式）
  el.style.setProperty("--font-scale", fontScale);
  el.style.setProperty("--space-scale", spaceScale);
}

export default function VisualTweakPanel() {
  const [vals, setVals] = useState(loadSaved);
  const [open, setOpen] = useState(false);
  const first = useRef(true);

  // 首次挂载 + 每次数值变化都写回 DOM 与 localStorage
  useEffect(() => {
    applyToDom(vals);
    if (first.current) {
      first.current = false;
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(vals));
    } catch (e) {
      /* ignore */
    }
  }, [vals]);

  const set = (key, v) => setVals((p) => ({ ...p, [key]: v }));
  const reset = () => {
    setVals({ ...DEFAULTS });
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      /* ignore */
    }
  };

  const row = (label, key, min, max, step, unit = "×") => (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 12,
          color: "#d1c48d",
          marginBottom: 4,
        }}
      >
        <span>{label}</span>
        <span style={{ color: "#ca9c42", fontVariantNumeric: "tabular-nums" }}>
          {(vals[key] * 100).toFixed(0)}%
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={vals[key]}
        onChange={(e) => set(key, parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: "#ca9c42", cursor: "pointer" }}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "#8b949e",
          marginTop: 2,
        }}
      >
        <span>{(min * 100).toFixed(0)}%</span>
        <span>{(max * 100).toFixed(0)}%</span>
      </div>
    </div>
  );

  return (
    <div
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        zIndex: 9999,
        fontFamily: "'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif",
      }}
    >
      {open && (
        <div
          style={{
            width: 248,
            marginBottom: 10,
            padding: 16,
            background: "rgba(20,30,30,0.96)",
            border: "1px solid rgba(212,168,83,0.3)",
            borderRadius: 12,
            boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
            backdropFilter: "blur(12px)",
            color: "#f2d89f",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.5 }}>
              视觉微调
            </span>
            <button
              onClick={() => setOpen(false)}
              title="收起"
              style={{
                background: "transparent",
                border: "none",
                color: "#8b949e",
                cursor: "pointer",
                fontSize: 16,
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
          {row("全局缩放", "zoom", 0.85, 1.5, 0.01)}
          {row("字号倍率", "fontScale", 0.85, 1.5, 0.01)}
          {row("间距倍率", "spaceScale", 0.8, 1.6, 0.01)}
          <button
            onClick={reset}
            style={{
              width: "100%",
              marginTop: 4,
              padding: "7px 0",
              background: "rgba(212,168,83,0.12)",
              border: "1px solid rgba(212,168,83,0.35)",
              borderRadius: 8,
              color: "#ca9c42",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            重置为默认
          </button>
          <div
            style={{
              marginTop: 10,
              fontSize: 10,
              color: "#8b949e",
              lineHeight: 1.5,
            }}
          >
            拖动滑块即时生效，设置自动保存。缩放=整体放大；字号/间距=单独微调使用设计 token 的文本与留白。
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        title="视觉微调面板"
        style={{
          width: 44,
          height: 44,
          borderRadius: "50%",
          background: "rgba(212,168,83,0.32)",
          border: "1px solid rgba(212,168,83,0.5)",
          color: "#f2d89f",
          fontSize: 20,
          cursor: "pointer",
          backdropFilter: "blur(8px)",
          boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginLeft: "auto",
        }}
      >
        {open ? "◧" : "⚙"}
      </button>
    </div>
  );
}
