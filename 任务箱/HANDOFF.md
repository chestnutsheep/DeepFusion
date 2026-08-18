# 执行交接说明（HANDOFF）— 给本地 CodeBuddy

> 读者：在本机继续维护 / 扩展 `deepfusion-desktop` 的 CodeBuddy（或人）。
> 目的：准确理解作者的设计意图，并**按 DeepFusion 的真实情况**把金融能力接进来，不踩红线。
> 配套文档：`ARCHITECTURE.md`（技术栈与模块边界）、`README.md`（快速上手）。

---

## 0. 一句话意图

把 Ubuntu/GNOME 桌面改造成 **「常驻 Dashboard 信息层 + 本机管家 Agent」**。Dashboard 永远贴在桌面上显示本机文件/存储、外部天气/新闻、以及（可选的）DeepFusion 金融数据；用户通过内置聊天窗命令管家做文件操作、生成汇报、调度任务、查询金融数据。

**DeepFusion 是「数据/计算提供方」，本项目是「桌面外壳 + 管家 + 消费方」。两者通过 HTTP 解耦，不得混仓、不得复制其计算代码。**

---

## 1. 仓库状态（交接时）

- 路径：`/workspace/deepfusion-desktop`（作者机）/ 你的 `~/.../deepfusion-desktop`
- Git：已 `init`，分支 `main`，首个提交 `0e2011c`（47 文件，工作树干净）。**未推远程**（作者沙箱无 GitHub 出口）。
- 当前能力：文件存储卡、外部信息卡（RSS+天气）、管家聊天（工具调用 + 兜底）、后台定时采集、Tauri 外壳配置、GNOME 桌面层脚本、systemd 自启单元。
- 缺一个图标文件已补：`src-tauri/icons/icon.png`（512 PNG 占位图，可后续替换为品牌图）。

### 验证状态分级
| 类别 | 状态 | 说明 |
|---|---|---|
| 后端逻辑（采集/工具/管家/调度） | ✅ 沙箱验证通过 | `compileall` + 启动 + 真实天气/新闻/目录 |
| 前端 SPA 构建 | ✅ 沙箱 `npm run build` 通过 | 已产出 `dashboard/dist` |
| Tauri 真机构建 | ⏳ 需你本机联网 | 需 cargo + webkit2gtk + npm install |
| 接入真实 LLM | ⏳ 需你填 `LLM_API_KEY` | 无 key 走离线正则兜底 |
| DeepFusion 金融 Widget | ⏳ 需你先跑 DeepFusion + 加 Widget | 桥接代码已就位，仅缺前端卡片 |

---

## 2. 本地 CodeBuddy 上手三件事

1. **读三份文档**：本文件 → `ARCHITECTURE.md` → `README.md`（按此顺序）。
2. **确认真实环境**：`python3 --version`（≥3.10）、`node -v`（≥18）、`cargo --version`、`which webkit2gtk`/系统库、`pgrep -f serve.py` 看 DeepFusion 是否在跑。
3. **跑通最小闭环**：按 §4 起后端 + 构建前端，确认 `/api/health` 正常、聊天窗能流式回复（离线兜底也行）。

---

## 3. 与 DeepFusion 的真实接入方式（红线区，务必照做）

### 3.1 DeepFusion 的真实形态（来自其 AGENTS.md）
- FastMCP 服务器 + `serve.py`（FastAPI，**端口 5173**），路由 `/api/tools/call`(POST)、`/api/tools/list`(GET)、`/api/logs`(GET)。
- 27 个 `tools/` 模块、共 **140 个 `@mcp.tool`**（2026-08-17 核对），全部返回 `str`（CSV/JSON/text 三类）。
- 4 个后台 daemon 线程（`_warmup_cycle_cache` / `_policy_collect_loop` / `_daily_data_collect_loop` / `_daily_report_loop`）。**后端进程死后线程全无 → 数据变陈旧，须 `restart_all.sh` 重启。**
- 红线：周期相位/信号公式/阈值/数据源配置/置信度计算**不可擅自修改**；改算法必须 +1 缓存版本号；新代码须保留旧输入输出接口。

### 3.2 本项目怎么接（已就位，勿重写）
- **只通过 HTTP 代理**，代码在 `butler/tools.py::_call_deepfusion`：
  - `POST {DEEPFUSION_URL}/api/tools/call`，body `{"name": tool, "arguments": {...}}`
  - `GET {DEEPFUSION_URL}/api/tools/list` 探测可用工具
  - `DEEPFUSION_URL` 默认 `http://localhost:5173`（= DeepFusion serve.py 端口）
- 管家工具 `call_deepfusion_tool` 把任意 DeepFusion 工具名透传；`list_tools` 列出 140 工具。

### 3.3 红线护栏（给本地 CodeBuddy 的硬约束）
- ❌ **不要**把 DeepFusion 的 `deep_fusion/`、`tools/`、`shared/` 代码 import 或复制到本仓库。
- ❌ **不要**为了"更好看/更统一"去改 DeepFusion 仓库里的计算定义（相位/评分/阈值）。那是 DeepFusion 维护者（量化方）的禁区。
- ✅ 要新增金融能力 → 在本仓库 `dashboard/src/widgets/` 加卡片，数据走 `call_deepfusion_tool` → HTTP → DeepFusion。
- ✅ 若发现 DeepFusion 端点形状变化（如返回包结构），**只改本仓库 `tools.py` 的解析层**，不碰 DeepFusion 源码。
- ✅ 两个仓库是独立 git 仓库。本仓库的提交/推送与 DeepFusion 无关。

### 3.4 推荐的金融 Widget 扩展路径（示例）
1. 用户本机先 `bash restart_all.sh` 起 DeepFusion（5173）。
2. 本仓库加 `dashboard/src/widgets/KondratievWidget.tsx`，挂载到 `WidgetGrid`。
3. 数据请求：前端 `postJSON('/api/tools/call', {name:'call_deepfusion_tool', arguments:{name:'kondratiev_cycle', arguments:{...}}})`，或直接加一个 `/api/widgets/finance` 后端路由内部调 `run_tool('call_deepfusion_tool', ...)`。
4. 解析 DeepFusion 返回的 str（CSV/JSON），渲染相位/资产配置/行业主线等。
5. 注意 DeepFusion 工具参数可能收到 `FieldInfo` 默认值（见其 `_val()` 约定）——经 HTTP 调用时已是普通 JSON，不受影响。

---

## 4. 构建与运行 SOP（在你本机）

```bash
# 1) 依赖
bash scripts/install.sh                 # 系统库 + Python venv(optional) 提示
npm install                             # 拉前端依赖 + @tauri-apps/cli

# 2) 后端（二选一，自动探测 FastAPI）
bash scripts/start_backend.sh           # 后台起 butler（端口 5180）
# 或： cd butler && python -m butler

# 3) 前端（开发预览）
cd dashboard && npm run dev             # vite dev，代理 /api + /ws → 5180

# 4) 真机桌面层（Tauri，需联网装 crate + webkit2gtk-4.1-dev）
bash scripts/gnome_setup.sh             # 隐藏原生桌面图标
npm run tauri dev                       # 无边框置底桌面层预览
bash scripts/gnome_window_tweak.sh      # X11 下压成 DESKTOP 窗口类型
# 正式打包： npm run tauri build  → .deb / AppImage

# 5) 开机自启
cp src-tauri/deepfusion-desktop.service ~/.config/systemd/user/
systemctl --user enable --now deepfusion-desktop
```

### 配置（`.env`，参考 `.env.example`）
```
LLM_API_KEY=sk-...            # 留空=离线兜底
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
DEEPFUSION_URL=http://localhost:5173
SCAN_DIRS=~/Documents;~/Downloads
WEATHER_LAT=39.9042
WEATHER_LON=116.4074
BUTLER_PORT=5180
```

---

## 5. 待办（按优先级，交给本地 CodeBuddy）

| 优先级 | 任务 | 依赖 | 备注 |
|---|---|---|---|
| P0 | `npm install` + `npm run tauri dev` 真机出桌面层 | 联网/webkit2gtk | 沙箱做不了，作者已补齐图标/脚本/配置 |
| P0 | 验证 DeepFusion 桥接 | DeepFusion 在跑 | `list_tools` 应回 140 工具；`call_deepfusion_tool` 应回真实数据 |
| P1 | 配 `LLM_API_KEY` 实测云脑工具调用链 | 联网/key | 无 key 已有正则兜底，先可跑 |
| P1 | 加 1~2 个金融 Widget（周期相位/资产配置） | DeepFusion 在跑 | 走 §3.4 路径，不碰 DeepFusion 源码 |
| P2 | 替换 `icon.png` 为品牌图标（`npx tauri icon`） | — | 当前是占位图 |
| P2 | Wayland 下桌面层化（X11 用 gnome_window_tweak.sh） | — | Wayland 需 `layer-shell` 扩展，待补脚本 |
| P3 | 推到 GitHub（见 §6） | 联网 | 作者沙箱无出口，已本地提交 |

---

## 6. 推送到 GitHub（本机一行命令）

```bash
cd /workspace/deepfusion-desktop        # 或你的本地路径
git remote add origin https://github.com/<用户名>/<仓库名>.git
git push -u origin main
```
> 作者机因无出口未能推送；本地提交已就绪（commit `0e2011c`）。
> 若用连接器 Token：`source ~/.codebuddy/skills/github-connector/scripts/get_token.sh github`，再 `git remote set-url origin https://oauth2:${GITHUB_TOKEN}@github.com/<用户名>/<仓库名>.git`。

---

## 7. 已知限制 / 坑（作者踩过，已规避）

- **端口对齐**：`dashboard/vite.config.ts` proxy → 5180；Tauri `devUrl` = 8080（与 DeepFusion 前端 dev 端口同号但不同源，互不冲突）。勿改 devUrl 为 5180，否则 Tauri dev 拉不到 vite。
- **FastAPI 与 stdlib 双实现契约须一致**：`main.py` 与 `server_std.py` 都必须提供 `/api/chat`(SSE) + `/ws`(WS)。改动一端要同步另一端。
- **stdio 日志污染**：本项目后端只给 Web 用，无 stdio MCP 通道，因此不需要 DeepFusion 那种 stderr-only 约束；但若未来把管家也暴露成 MCP，记得日志走 stderr。
- **DeepFusion 不在时**：`call_deepfusion_tool` 返回友好提示而非崩溃；`list_tools` 回占位说明。前端金融 Widget 需优雅降级。
- **A 股交易日**：DeepFusion 行业日行情仅交易日有数据，判断新鲜度以最后交易日为准（非日历日）——扩展金融 Widget 时注意。
