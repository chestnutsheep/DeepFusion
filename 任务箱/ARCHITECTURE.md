# DeepFusion Desktop — 技术栈与架构

> 定位：把一台 Ubuntu/GNOME 桌面改造成「常驻 Dashboard 信息层 + 本机管家 Agent」的桌面外壳。
> 它**不重复实现**金融计算，而是通过 HTTP 复用 DeepFusion 已有的 140 个 MCP 工具。
> 本文档描述技术栈、模块边界与数据流，供维护者（含本地 CodeBuddy）准确理解系统形态。

---

## 1. 系统形态（三层）

```
┌─────────────────────────────────────────────────────────────┐
│  Tauri v2 原生窗口 (src-tauri/)                               │
│  decorations:false · alwaysOnBottom · skipTaskbar · focus:false │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  React SPA (dashboard/) — 桌面图层 UI                    │  │
│  │   ├─ WidgetGrid：文件存储卡 / 外部信息卡（可点击弹详情）│  │
│  │   └─ ChatDock：与管家 Agent 对话的主入口                │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────┘
                                 │ HTTP/WS (fetch + WebSocket)
┌───────────────────────────────┴─────────────────────────────┐
│  Python Butler 后端 (butler/, 端口 5180)                      │
│   ├─ collectors/  file_storage + external（RSS/Open-Meteo） │
│   ├─ scheduler.py 后台守护线程（定时采集入库）              │
│   ├─ agent/      管家 LLM 循环 + 离线兜底 + 工具调度        │
│   ├─ tools.py    TOOL_SPECS + run_tool 分发 + DeepFusion 代理│
│   ├─ server_std.py / main.py  REST+SSE+WS（FastAPI 可选）  │
│   └─ db.py SQLite (~/.cache/deepfusion_desktop/butler.db)   │
└───────────────────────────────┬─────────────────────────────┘
                                 │ HTTP 代理 (POST /api/tools/call)
┌───────────────────────────────┴─────────────────────────────┐
│  DeepFusion (独立仓库, 端口 5173)  ← 仅消费，不改动          │
│   FastMCP 140 工具 + FastAPI serve.py + React 看板(8080)    │
└─────────────────────────────────────────────────────────────┘
```

**关键原则：deepfusion-desktop 与 DeepFusion 是「消费方 / 提供方」关系，通过 HTTP 解耦。**
deepfusion-desktop 绝不 import 或复制 DeepFusion 的 Python 代码，因此**天然不触碰 DeepFusion 的红线计算定义**（见 HANDOFF.md §5）。

---

## 2. 技术栈清单

| 层 | 技术 | 说明 |
|---|---|---|
| 桌面外壳 | Tauri v2 + Rust | 无边框 / 置底 / 跳任务栏；把 SPA 包成原生桌面层 |
| 前端 | React 18 + Vite + TypeScript + Zustand | Widget 网格 + 聊天窗；Glassmorphism 暗色主题 |
| 前端实时 | WebSocket 优先 + SSE 兜底 + 轮询兜底(15s) | `subscribeWidgets` / `streamChat` 三级容错 |
| 后端 | Python 3.10+（stdlib 优先） | `http.server` 零依赖可跑；FastAPI 存在时自动升级 |
| 后端实时 | SSE（`POST /api/chat`）+ WebSocket（`/ws`） | 聊天流式 + Widget 推送 |
| 持久化 | SQLite（WAL） | DB-first、增量追加，遵循 DeepFusion 的 freshness 理念 |
| 调度 | 标准库线程 `scheduler.py` | 守护线程按 cron 间隔跑采集/分析 |
| 管家大脑 | OpenAI 兼容 LLM（lazy import `openai`） | 工具调用循环（≤6 轮）；无 key 时正则兜底 |
| 外部数据 | RSS（stdlib `xml.etree`）+ Open-Meteo（无 key） | 天气/新闻，离线可达 |
| 金融数据 | DeepFusion HTTP 代理 | `call_deepfusion_tool` 复用 140 个 MCP 工具 |

---

## 3. 模块边界（后端 `butler/`）

| 模块 | 职责 | 不越界 |
|---|---|---|
| `config.py` | env/.env → `Settings` 单例 | 只读配置，不触 IO |
| `db.py` | SQLite schema + `get_conn`/`init_db`/`log` | 不写业务 SQL 外逻辑 |
| `state.py` | 进程内 Widget 缓存 + SSE pub/sub | 不持久化 |
| `collectors/file_storage.py` | 扫描 `SCAN_DIRS`，记录每目录大小/文件数，保留 50 最近文件 | 只采集不推送 |
| `collectors/external.py` | RSS + Open-Meteo 天气；`collect()` 删除重建派生视图 | 只用无 key 接口 |
| `tools.py` | 9 个管家工具 + `run_tool` 分发 + `_call_deepfusion` 代理 | 不持有状态 |
| `scheduler.py` | 注册 interval/once 任务 + 守护线程 | 只调度不实现业务 |
| `agent/` | `SYSTEM_PROMPT` + `_llm_stream`（tool-calls 循环）+ `_fallback` | LLM 异常不崩主循环 |
| `server_std.py` | 零依赖 `ThreadingHTTPServer`（REST+SSE+静态） | 仅当 FastAPI 不可用时启用 |
| `main.py` | FastAPI 版（REST+WS+静态挂载），与 stdlib 版契约一致 | 二选一，进程内只跑一个 |
| `__main__.py` | `python -m butler` 入口（自动探测 FastAPI） | — |

---

## 4. API 契约（端口 5180）

| 方法 | 路径 | 用途 | 返回 |
|---|---|---|---|
| GET | `/api/health` | 健康检查 | `{status, version, deepfusion}` |
| GET | `/api/tools/list` | 列出管家工具 spec | `{tools: TOOL_SPECS}` |
| POST | `/api/tools/call` | 调管家工具 | `{name, result}` |
| GET | `/api/widgets` | 全部 Widget 快照 | `{file_storage, external}` |
| GET | `/api/widgets/file_storage` | 文件存储卡数据 | 见 §6 |
| GET | `/api/widgets/external` | 外部信息卡数据 | 见 §6 |
| GET | `/api/chat/history` | 聊天历史 | `[{role,content}]` |
| POST | `/api/chat` | 流式聊天（SSE） | `data: {json}\n\n` … `data: [DONE]` |
| GET | `/api/logs` | 系统日志 | `[{level,msg,ts}]` |
| WS | `/ws` | 实时通道（聊天帧 + Widget 推送） | JSON 帧 |

**前端连接策略**（`src/lib/api.ts`）：
- `VITE_API_BASE` 为空 → 同源（vite dev 代理 / Tauri 同源）；设 `http://localhost:5180` 用于 Tauri 内嵌构建。
- `streamChat`：先试 WebSocket `/ws`，2.5s 超时或失败降级 SSE `POST /api/chat`。
- `subscribeWidgets`：先试 WS，失败降级每 15s 轮询 `/api/widgets/*`。

---

## 5. 数据与 Widget 形状

`file_storage.latest()`（每目录一条，recents 按 mtime 倒序取 50）：
```json
[
  {"dir": "/home/u/Documents", "taken_at": "2026-08-17 02:00:00",
   "total_bytes": 5242880000, "file_count": 1234,
   "recents": [{"path": "/home/u/Documents/x.md", "size": 2048, "mtime": 1.75e9, "ext": ".md"}]}
]
```

`external.latest()`（news 截前 40 条；weather 为整行或 null）：
```json
{"news": [{"category": "news", "source": "https://...", "title": "...",
           "link": "...", "summary": "摘要…", "published": "…", "fetched_at": "…"}],
 "weather": {"category": "weather", "summary": "Beijing 当前 晴，22.1°C，湿度 85%，风速 0.4 km/h",
             "payload": "{\"temperature\":22.1,\"humidity\":85,\"wind\":0.4,\"code\":0,\"time\":\"…\"}"}}
```
> 天气的人类可读串在 `weather.summary`；原始数值 JSON 在 `weather.payload`。news 有 `summary`（截断描述），非 `description`。

Widget 键：`file_storage`、`external`（store.ts 的 `setWidgets` 同时兼容 `file_storage`/`fileStorage`）。

---

## 6. DeepFusion 桥接契约（最重要）

`butler/tools.py::_call_deepfusion` 是**唯一**与 DeepFusion 耦合的代码：

```python
# tools.py
payload = {"name": name, "arguments": arguments or {}}
url = settings.deepfusion_url.rstrip("/") + "/api/tools/call"   # 默认 http://localhost:5173
# → urllib POST，60s 超时，返回截断至 6000 字符的原始响应字符串
```

`butler/config.py::Settings.deepfusion_url` 默认值 = `http://localhost:5173`（即 DeepFusion `serve.py` 端口）。

- 工具 `list_tools` 通过 `GET {deepfusion_url}/api/tools/list` 探测可用金融工具。
- 工具 `call_deepfusion_tool` 把任意 DeepFusion MCP 工具名 + 参数透传过去。
- 耦合面**只有**：一个 URL + 两个 REST 端点（`/api/tools/call`、`/api/tools/list`）。
- 不依赖 DeepFusion 任何 Python 内部实现 —— DeepFusion 升级/重构不影响本桥接。

> 这正是「根据 DeepFusion 真实情况接入」的核心：DeepFusion 的 `serve.py` 已暴露这两端点（前端 `dashboard/` 走 `services/mcp.js` 调 `/api/tools/call`）。本项目的管家直接复用同一 HTTP 契约，无需另起协议。

---

## 7. 端口分配（避免冲突）

| 服务 | 端口 | 来源 |
|---|---|---|
| DeepFusion `serve.py` | 5173 | DeepFusion 固定 |
| DeepFusion 前端 dev | 8080 | DeepFusion 固定（= Tauri `devUrl`） |
| DeepFusion 各 DB | — | `cycle_cache.db` 等（不动） |
| **Butler 后端** | **5180** | `BUTLER_PORT`（默认） |
| Butler vite dev | 8080（vite 默认被 Tauri 占用时回退） | `dashboard/vite.config.ts` proxy → 5180 |

---

## 8. 已就绪 / 待真机

**已离线验证（沙箱内完成）**：后端 `compileall` 通过、启动、同源服务 SPA、聊天 SSE 流式 + 真实北京天气 + 39 条新闻、文件存储卡真实统计、图标生成、GNOME 脚本语法全部通过。

**必须在本机（联网 Ubuntu）完成**：`npm install`（拉 `@tauri-apps/cli`）、`npm run tauri dev/build`（需 cargo + `webkit2gtk-4.1-dev`）、配置 `LLM_API_KEY`、运行 DeepFusion `restart_all.sh` 后验证金融 Widget。
