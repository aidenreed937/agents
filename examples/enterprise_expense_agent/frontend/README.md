# Enterprise Expense Agent · 前端控制台 (React + Vite + Zustand)

采用 **React 18 + Vite 6 + Zustand 5** 构建的现代化状态机控制台，与后端 FastAPI + LangGraph 运行时完全物理分离。

---

## 一、 系统架构与通信机制

```
[ 前端 React 控制台 (Port: 3000 / 5173) ]
  ├── 状态脚手架 (Zustand: useExpenseStore / useHitlStore)
  ├── 交互组件群 (EmployeePortal / HitlCenter / TopologyViewer)
           │
           │  1. SSE 流式通信: GET /api/expense/submit-stream (实时节点推进事件)
           │  2. REST API: POST /api/expense/submit (同步报销提报)
           │  3. REST API: GET  /api/expense/tasks (人在回路待审批工单)
           │  4. REST API: POST /api/expense/resume (Command(resume) 审批唤醒)
           ▼
[ 后端 API 网关 (FastAPI, Port: 8000) ]
           │
           ▼
[ LangGraph 状态图引擎 (EnterpriseExpenseWorkflow) ]
           │
           ▼
[ 持久化检查点 (LangGraphFileCheckpointer / PostgresSaver) ]
```

---

## 二、 工程目录结构

```
frontend/
├── index.html                 # Vite 挂载入口模板
├── vite.config.js             # Vite 配置文件 (@vitejs/plugin-react)
├── package.json               # 项目依赖声明 (react, zustand, vite 等)
├── dist/                      # Vite 生产构建产物目录
└── src/
    ├── main.jsx               # React 根挂载点
    ├── App.jsx                # 顶层应用骨架与轮询控制器
    ├── App.css                # 现代化暗色主题与响应式样式
    ├── store/                 # [核心状态脚手架 (Zustand)]
    │   ├── useExpenseStore.js # 报销表单、SSE 实时事件流与 6 阶段流水线状态
    │   └── useHitlStore.js    # 人在回路 (HITL) 待办轮询、审批详情与特批唤醒
    ├── services/
    │   └── api.js             # 统一 REST 与 EventSource (SSE) 协议客户端
    └── components/
        ├── Header.jsx         # 顶部导航、后端地址动态配置与健康指示器
        ├── Navigation.jsx     # Tab 切换栏与待办红色 Badge 计数
        ├── employee/          # 员工报销模块
        │   ├── EmployeePortal.jsx
        │   ├── PresetSelector.jsx
        │   ├── ExpenseForm.jsx
        │   ├── PipelineVisualizer.jsx
        │   ├── LiveTerminal.jsx
        │   └── ResultCard.jsx
        ├── hitl/              # 人在回路审批模块
        │   ├── HitlCenter.jsx
        │   ├── TaskTable.jsx
        │   └── TicketDetailDrawer.jsx
        └── graph/             # 拓扑可视化模块
            └── TopologyViewer.jsx
```

---

## 三、 运行与开发方式

### 方式 1：一键启动（全自动编译与托管）

在项目根目录执行：
```bash
./examples/enterprise_expense_agent/start_demo.sh
```
脚本会自动检查并执行 `pnpm build`，并启动本地轻量服务托管 `dist/` 生产资源（端口 3000）。

### 方式 2：开发热重载模式 (HMR)

```bash
cd examples/enterprise_expense_agent/frontend
pnpm install
pnpm dev
```
本地实时开发服务器将运行在 `http://127.0.0.1:3000`，支持毫秒级热更新。

### 方式 3：生产打包构建

```bash
cd examples/enterprise_expense_agent/frontend
pnpm build
```

---

## 四、 核心状态脚手架特性

1. **确定性状态机响应绑定**：
   - 通过 `useExpenseStore`，将 LangGraph 逐级吐出的节点事件（`security_guardrail`、`parse_intent`、`fetch_data_assets`、`cross_validate_claim`、`governance_check`、`create_draft`）映射为确定的 UI 节点状态（`waiting` / `running` / `done` / `interrupted` / `blocked`）。
2. **人在回路无缝协同**：
   - 通过 `useHitlStore` 实现每 6 秒自动探活并检索 `PAUSED_HITL` 状态的待办工单；
   - 提取不可篡改数字契约哈希（`claim_version_hash`）展示给审批人，提交审批时向 LangGraph 派发 `Command(resume=...)` 原位恢复执行。
3. **零侵入通信解耦**：
   - 前端可在界面直接配置不同的后端网关地址（如 `http://127.0.0.1:8000`），实时检测健康状态并平滑切换。
