# DeepFusion Desktop

把 **DeepFusion**（Python MCP 服务器 + React 看板的中国金融市场分析系统）从「浏览器标签页」升级为
**常态化桌面层 + 桌面管家 Agent**。本项目是叠加在 DeepFusion 之上的轻量外壳，提供三件事：

1. **桌面层形态** —— 用 Tauri 把看板变成无边框、置底、跳过任务栏的常驻桌面（替代丑陋的原生 GNOME 桌面）。
2. **可点击弹开的数据组件** —— 文件/存储、外部信息(RSS+天气) 等 Widget，点击展开详情抽屉。
3. **桌面管家 Agent（聊天窗）** —— 右下角常驻聊天入口，连云端 LLM 当管家，能读/写文件、生成汇报、登记定时任务，
   并**代理调用 DeepFusion 的 140+ 金融工具**。

> 后端默认 **零依赖（纯标准库）** 即可运行；装了 `fastapi/uvicorn` 后用 WebSocket 获得完整体验。
> 云端 LLM Key 不填也能用（离线规则应答），填了才用大模型理解自然语言。

## 文档导航

| 文档 | 给谁看 | 内容 |
|---|---|---|
| [HANDOFF.md](./HANDOFF.md) | 后续维护者 / 本地 CodeBuddy | **执行交接**：设计意图、交付状态、DeepFusion 红线护栏、构建 SOP、待办 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构 / 接入方 | 技术栈、模块边界、API 契约、Widget 数据形状、DeepFusion 桥接契约 |
| [README.md](./README.md) | 使用者 | 快速上手 A/B/C、配置、GNOME 桌面层说明 |

---

## 与 DeepFusion 的关系

DeepFusion 已经有：后台定时采集、`SQLite` 落库、React 看板、140 个 `@mcp.tool` 金融工具。
本项目**不重复造轮子**，而是新增一个 `butler` 服务：

- 复用 DeepFusion 的采集/落库范式（DB-first、增量追加、派生存量 TTL）。
- 通过 `POST {DEEPFUSION_URL}/api/tools/call` **代理** DeepFusion 工具，把金融能力接入桌面管家。
- 新增 DeepFusion 没有的：**本机文件/存储 Widget、外部信息 Widget、管家聊天 Agent**。

```
┌──────────────────────────────────────────────────────────┐
│  Tauri 无边框置底窗口 = 桌面层                               │
│  React 看板 (Widget 网格 + 右下角聊天窗)                     │
└───────────────────────┬──────────────────────────────────┘
                        │ REST / WebSocket (localhost:5180)
┌───────────────────────┴──────────────────────────────────┐
│  butler 后端 (FastAPI 或 stdlib http.server)                │
│   ├─ 调度 APScheduler-like 线程：file_storage / external     │
│   ├─ 采集器 → SQLite（DB-first 增量）                        │
│   ├─ Agent：云端 LLM 工具调用 + 本机文件/汇报/调度            │
│   └─ 代理 DeepFusion /api/tools/call                        │
└──────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 方式 A：浏览器看板（最简单，立即可用）
```bash
bash scripts/install.sh
bash scripts/restart_all.sh
# 打开 http://localhost:8080
```

### 方式 B：Tauri 桌面层（替代原生桌面）
```bash
bash scripts/install.sh
npm install                            # 拉取 @tauri-apps/cli（根目录 package.json）
npm run tauri dev                      # 开发预览：无边框置底桌面层
npm run tauri build                    # 打包 .deb / AppImage（图标已就绪）
```
> 图标已内置占位图 `src-tauri/icons/icon.png`（仓库自带，build 不再缺资源）。
> 想换 logo： `npx tauri icon your.png` 重新生成整套图标。
> 编译需联网（cargo 拉 tauri crate + npm 依赖 + 系统 `webkit2gtk` 库），请在你的 Ubuntu 上执行。

### 方式 C：仅后端（无界面，给外部调用）
```bash
python3 -m butler                      # http://localhost:5180
curl http://localhost:5180/api/health
```

---

## 配置（`.env`）

复制 `.env.example` 为 `.env`。关键项：

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` | 云端 LLM（管家大脑）。留空=离线规则应答 |
| `DEEPFUSION_URL` | DeepFusion 后端地址，默认 `http://localhost:5173` |
| `SCAN_DIRS` | 文件/存储监控目录，`;` 分隔，默认 `~` |
| `RSS_FEEDS` | 外部资讯源，`;` 分隔 |
| `WEATHER_LAT/LON/CITY` | Open-Meteo 天气（免 Key） |
| `BUTLER_PORT` | 后端端口，默认 `5180` |
| `FILE_SCAN_INTERVAL_MIN` / `EXTERNAL_SCAN_INTERVAL_MIN` | 采集周期 |

---

## 桌面管家能做什么

在右下角聊天窗里直接说（离线也能用）：

- 「生成汇报」 → 汇总本机存储/外部信息，存到 `~/deepfusion_desktop_reports/`
- 「列出 ~ 目录」 / 「读取 /path/to/file」 / 「搜索 report 文件」
- 「系统状态」 → 采集/任务/LLM 配置概览
- 「每天生成汇报」 / 「每 30 分钟采集外部信息」 → 登记定时任务
- 提到股票/周期/行业/宏观 → 提示并通过代理调用 DeepFusion 工具

配置 `LLM_API_KEY` 后，管家会用大模型理解更复杂的自然语言并自动编排工具。

---

## GNOME / 桌面层说明

窗口已由 `src-tauri/tauri.conf.json` 设为 `alwaysOnBottom + decorations:false + skipTaskbar:true + focus:false`，
作为背景层常驻。本仓库附带脚本把原生 GNOME 真正改造成 Dashboard 背景：

```bash
# 1) 隐藏原生桌面图标（X11 / Wayland 均可生效）
bash scripts/gnome_setup.sh
# 2) 一键启动：后端(butler) + Tauri 桌面层
bash scripts/start_desktop.sh
# 3) 把窗口压到桌面层（仅 X11：需登录 "Ubuntu on Xorg"）
bash scripts/gnome_window_tweak.sh
# 撤销改动：
bash scripts/gnome_restore.sh
```

⚠ **会话类型**：窗口"压到桌面层 / 设为 DESKTOP 类型"依赖 **X11**。现代 Ubuntu 默认 Wayland，
`wmctrl`/`xprop` 无效——请在登录界面选 **Ubuntu on Xorg**。若坚持 Wayland，本方案退化为
"无边框置底窗口"（仍可用，只是不能用窗口类型技巧），或直接用方式 A 浏览器看板。

🔁 **开机自启**：`src-tauri/deepfusion-desktop.service` 已写好（systemd --user 单元）。
```bash
mkdir -p ~/.config/systemd/user
cp src-tauri/deepfusion-desktop.service ~/.config/systemd/user/
systemctl --user enable --now deepfusion-desktop
```

---

## 目录结构

```
deepfusion-desktop/
├── butler/                 # 后端（stdlib-first，FastAPI 可选）
│   ├── config.py  db.py  state.py  tools.py  scheduler.py
│   ├── collectors/        # file_storage.py / external.py
│   ├── agent/             # __init__.py（管家 LLM + 工具调用 + 离线兜底）
│   ├── server_std.py      # 零依赖 HTTP 服务（SSE 聊天）
│   └── main.py            # FastAPI 生产入口（WebSocket）
├── dashboard/             # React 18 + Vite + TS 看板
│   └── src/ widgets/ chat/ store/ lib/
├── src-tauri/             # Tauri v2 桌面壳（无边框置底）
├── scripts/               # install / restart_all / start_backend / start_desktop
│                         # gnome_setup / gnome_window_tweak / gnome_restore
├── package.json           # 根：tauri CLI 脚本 (npm run tauri dev|build)
└── README.md
```

## 安全

- 所有文件操作为只读/显式写入，**绝不删除用户未确认的文件**。
- API Key 仅存于本地 `.env`，不入库、不上报。
- 后端默认监听 `0.0.0.0`；若在公网机器运行，请改用 `127.0.0.1` 或加反向代理鉴权。
