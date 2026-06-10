---
应用: 始终
---

# DeepFusion 项目规则与 AI 工作流程

> **版本**: 1.1  
> **适用范围**: 所有参与 DeepFusion 前端开发的 AI 助手 
> **核心原则**: 数据驱动 · 配置先行 · 硬编码零容忍 · 遵循 Superpowers 流程 · 卡片自适应布局

---

## 一、通用代码规范

### 1.1 代码风格

| 规则 | 要求 |
|------|------|
| 缩进 | 2 空格（禁止 Tab） |
| 行宽 | 100 字符 |
| 引号 | 统一使用单引号 `'`，JSX 中使用双引号 `"` |
| 分号 | 必须加分号 `;` |
| 尾逗号 | 对象/数组最后一个元素加逗号 |
| 换行符 | LF（Unix） |

### 1.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `DataCard.jsx` |
| 工具函数文件 | camelCase | `useMCP.js` |
| 配置表文件 | camelCase 或 kebab-case | `kitchin.js`, `macro-snapshot.js` |
| 组件名称 | PascalCase | `function DataCard() {}` |
| Hook 名称 | camelCase 以 `use` 开头 | `useMCP` |
| 常量 | 全大写 + 下划线 | `PHASE_WEIGHTS` |
| CSS 类名 | kebab-case | `.snapshot-card`, `.main-content` |

### 1.3 注释规范

```jsx
/**
 * 组件说明 - 描述用途
 * @param {string} label - 指标名称
 * @param {number} value - 当前值
 * @returns {JSX.Element}
 */
```

- 每个组件必须有 JSDoc 注释。
- 复杂业务逻辑必须有行内注释。
- 临时解决方案必须标注 `// TODO:` 并说明原因。

### 1.4 禁止事项（红线）

- ❌ 禁止在组件中硬编码数值、阶段名、颜色值
- ❌ 禁止直接使用 `fetch` 调用 MCP（必须用 `useMCP`）
- ❌ 禁止使用内联 `style`（除非动态计算定位）
- ❌ 禁止在非 `configs/` 目录中创建指标配置
- ❌ 禁止删除 `global.css` 中的任何 CSS 变量
- ❌ 禁止在组件中直接计算日期字符串（必须用 `utils/date.js`）
- ❌ 禁止为卡片设置固定宽度或固定高度（必须由父容器决定）

---

## 二、Superpowers 工作流程（16 Skills）

**所有代码修改必须遵循以下 Superpowers 技能流程，缺一不可。**

每个技能对应一个独立的步骤，AI 在输出时必须按顺序标记。

### 2.1 技能清单

| 序号 | 技能名称 | 说明 |
|------|---------|------|
| 1 | `brainstorm` | 理解需求，拆解问题，提出多个可行方案 |
| 2 | `plan` | 制定详细修改计划，列出涉及文件、预估影响 |
| 3 | `research` | 检查现有代码、数据接口、样式变量，确认可行性 |
| 4 | `design` | 设计组件结构、数据流、UI 布局（可输出简单 ASCII 草图） |
| 5 | `implement` | 按照计划编写代码，保持与现有架构一致 |
| 6 | `test` | 编写或运行测试用例（单元测试、手动测试清单） |
| 7 | `debug` | 定位并修复错误，记录原因与解决方案 |
| 8 | `review` | 自我审查代码风格、硬编码、性能问题 |
| 9 | `optimize` | 优化性能、可读性、复用性（如提取重复逻辑） |
| 10 | `document` | 更新相关文档、配置表注释、JSDoc |
| 11 | `style` | 确保样式响应式、主题变量正确、无固定尺寸 |
| 12 | `accessibility` | 检查键盘导航、焦点管理、ARIA 标签 |
| 13 | `performance` | 分析渲染次数、数据缓存策略（React Query） |
| 14 | `security` | 避免 XSS、敏感信息泄露（如 API key） |
| 15 | `deploy` | 准备构建产物、验证生产环境配置 |
| 16 | `archive` | 总结修改内容，记录到变更日志 |

### 2.2 强制输出格式

在执行任何任务时，AI 必须按顺序输出如下结构化内容：

```markdown
## 🧠 Skill 1: Brainstorm
[需求理解与方案对比]

## 📋 Skill 2: Plan
[具体修改计划]

## 🔍 Skill 3: Research
[现有代码调研结果]

## 🎨 Skill 4: Design
[组件/UI 设计草图或数据流说明]

## ⚙️ Skill 5: Implement
[代码实现，分文件展示关键片段]

## ✅ Skill 6-16: (根据需要选择执行)
- Test: [验证清单]
- Debug: [如有错误记录]
- Review: [自查结果]
...
```

**例外**：纯文本修改、简单 bug 修复可省略部分技能，但仍需保留 `Plan` → `Implement` → `Test`。

---

## 三、技术栈与首选工具

### 3.1 核心依赖

| 类别 | 首选工具 | 备用方案 | 禁止 |
|------|---------|---------|------|
| UI 框架 | React 18 | — | 其他框架 |
| 构建工具 | Vite | — | Webpack |
| 路由 | React Router DOM v6 | — | — |
| 状态管理 | TanStack Query（服务端状态） | Zustand（全局 UI 状态） | Redux |
| 图表 | ECharts + echarts-for-react | — | Recharts, Chart.js |
| 主题 | next-themes | — | — |
| 侧边栏 | react-pro-sidebar | — | — |
| 悬浮卡片 | @floating-ui/react | — | — |
| 样式 | CSS 变量 + 全局 CSS | CSS Modules | Tailwind, styled-components |
| HTTP 请求 | 项目内 `mcp.js` + `useMCP` | — | axios, fetch 直接调用 |

### 3.2 样式规则

- **所有颜色**必须使用 CSS 变量（如 `var(--accent-gold)`），不允许写十六进制或 rgb 值。
- **间距**使用 `rem` 或 CSS 变量（如 `var(--radius-lg)`）。
- **响应式**必须提供媒体查询（至少 768px 断点）。
- **卡片边框**统一使用 `border: 1px solid rgba(212,168,83,0.5);`。
- **指标卡片（DataCard）无固定宽高**：卡片本身不应设置 `width` 或 `height`，应由父容器（如 `DataGrid` 的 `grid-template-columns`、`flex`）决定卡片尺寸。卡片内部使用 `padding` 撑开，内容自然换行。

**DataCard 示例样式（正确）**：
```css
.data-card {
  background: var(--bg-panel);
  border: 1px solid rgba(212,168,83,0.5);
  border-radius: var(--radius-lg);
  padding: 16px;          /* 内边距，不设置宽高 */
  display: flex;
  flex-direction: column;
  gap: 8px;
}
```

**错误示例**：
```css
.data-card {
  width: 200px;          /* 禁止 */
  height: 150px;         /* 禁止 */
}
```

### 3.3 数据获取规则

- **唯一入口**: `useMCP(toolName, args)`
- **缓存策略**: 宏观数据 24 小时，微观数据 8 小时（由 hook 内部根据工具名自动判断）
- **错误处理**: 必须提供 `isLoading` 和 `error` 状态，不允许直接假设数据存在。

```jsx
const { data, isLoading, error } = useMCP('macro_gdp', { limit: 1 });
if (isLoading) return <div>加载中...</div>;
if (error) return <div>加载失败</div>;
```

---

## 四、项目架构规定

### 4.1 目录结构（强制）

```
src/
├── configs/            # 所有指标配置表（唯一数据字典）
├── components/
│   ├── common/         # DataCard, DataGrid, DataChart, StatusBar, TooltipIcon
│   ├── Macro/
│   ├── Meso/
│   ├── Micro/
│   ├── Global/
│   └── Policy/
├── pages/              # 路由页面组件
├── hooks/              # useMCP.js (唯一)
├── layouts/            # MainLayout.jsx
├── lib/                # react-query 配置
├── services/           # mcp.js (唯一)
└── styles/             # global.css (唯一)
```

### 4.2 配置表驱动

- **所有指标**（宏观快照、周期指标、行业估值、财务指标等）必须由 `configs/` 下的配置表定义。
- **不允许**在组件中直接写指标名称或单位。
- 配置表格式示例：

```js
// configs/kitchin.js
export const KITCHIN_CONFIG = {
  queryKey: 'data_kitchin',
  chartSeries: [{ key: 'inventory_yoy', name: '库存同比', color: '#f85149' }],
  metrics: [
    { key: 'inventory_yoy', label: '库存同比', unit: '%', tooltip: '解释文本' }
  ]
};
```

### 4.3 数据字典一致性

- 所有 MCP 工具返回的 JSON 字段名必须与 `configs/` 中的 `key` 严格一致。
- 如需新增字段，必须先更新数据字典文档（`docs/data-dictionary.md`），再修改配置表。

### 4.4 组件复用规则

- 单个指标卡片必须使用 `<DataCard>`。
- 指标网格必须使用 `<DataGrid>`。
- 图表必须使用 `<DataChart>`。
- 周期状态条必须使用 `<StatusBar>`。
- **禁止**自己写 `div` + `span` 拼指标卡。

### 4.5 布局自适应规则

- 所有卡片容器（如 `DataGrid` 的网格）必须使用 CSS Grid 或 Flex 的 `auto-fit / minmax`，不得写死 `width`。
- 示例：
```css
.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}
```
- 卡片内部内容若溢出，使用 `word-break: break-word` 或 `overflow-wrap: break-word`。

---

## 五、提交前检查清单

AI 在最终输出代码前，必须自查：

- [ ] 无硬编码颜色、数值、阶段名
- [ ] 所有文本使用 CSS 变量或配置表
- [ ] 所有组件使用 `<DataCard>` / `<DataChart>` 等通用组件
- [ ] 无 `console.log` 或其他调试代码
- [ ] 无内联 `style`（动态定位除外）
- [ ] 卡片无固定宽高，完全由父容器决定
- [ ] 响应式布局（至少 768px 断点）
- [ ] 所有新增文案都有 `TooltipIcon` 解释（或至少预留 `tooltip` 字段）
- [ ] 遵循 Superpowers 流程（输出过至少 `Plan` → `Implement` → `Test`）

---

## 六、附录：常用 CSS 变量速查

| 变量 | 用途 | 示例值 |
|------|------|--------|
| `--text-primary` | 主要文字颜色 | `#E8E0D0` |
| `--text-secondary` | 次要文字 | `#B0A898` |
| `--accent-gold` | 强调色、边框 | `#D4A853` |
| `--accent-red` | 上涨/正向（数值） | `#f85149` |
| `--accent-green` | 下跌/负向（数值） | `#3fb950` |
| `--border-subtle` | 默认边框 | `rgba(212,168,83,0.12)` |
| `--radius-lg` | 大圆角 | `18px` |
| `--bg-panel` | 卡片背景 | `rgba(43,74,74,0.35)` |

---

## 七、更新与版本

- 本文件随项目架构演进同步更新。
- 每次修改 `AGENTS.md` 后，必须通知所有协作者。
- AI 助手在收到冲突指令时，以本文件为最高优先级。

**最后更新**: 2026-06-08  
**维护者**: DeepFusion 项目组
```

将此文件保存为项目根目录下的 `AGENTS.md`（或 `CLAUDE.md`），AI 助手将自动遵循上述 Superpowers 流程和卡片自适应布局规则。