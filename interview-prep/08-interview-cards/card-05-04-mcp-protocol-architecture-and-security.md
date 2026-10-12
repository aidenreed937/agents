# 面试卡：MCP 协议架构剖析与企业级安全沙箱隔离

**模块**：05-agent-engineering ｜ **难度**：高级 ｜ **熟练度**：B

---

### 1. 30 秒电梯回答
MCP 协议的核心是**将大模型宿主应用与外部数据源和工具标准化解耦**。
- **三层架构解耦**：由 **Host**（应用协调者）管理多个 **Client**（协议中继），通过 Stdio/SSE 传输协议标准化连接外部 **Server**（提供 Prompts、Resources 与 Tools）；
- **沙箱与权限防御**：企业落地推行最小权限原则与双重沙箱，Server 隔离在容器/子进程内并设工具调用白名单，严防间接提示词注入触发任意命令执行与数据外发。

---

### 2. 深入原理
1. **MCP 核心架构与角色关系**：
   - **Host**：承载 Agent 逻辑的主应用（如 Claude Desktop、Cursor、自研 Agent 平台）。它不直接与外部资源打交道，而是管理多个 MCP Client。
   - **Client**：与 Server 维持 1:1 连接的协议客户端，负责协议协商、请求路由与认证。
   - **Server**：轻量级外部适配器，向 Client 声明能力：
     - `Prompts`：预设的提示词模板；
     - `Resources`：只读的外部数据流或上下文（如 Git 仓库文件、数据库 Schema）；
     - `Tools`：模型可执行的函数（带有 JSON Schema 说明）。
2. **传输层协议（Transports）**：
   - **Stdio Transport**：基于本地标准输入输出（stdin/stdout）通信。适用于本地 IDE/桌面客户端拉起本地 CLI 进程，延迟极低，生命周期随 Host 销毁。
   - **SSE / HTTP Transport**：基于网络长连接通信。适用于远程微服务或企业集中式 MCP 网关，支持跨网络分布式部署与集中式认证。
3. **调用生命周期**：
   - 初始化握手（`initialize`）交换协议版本与功能特性（Capabilities）→ 工具发现（`tools/list`）返回可用工具清单并注入 LLM 上下文 → 模型决定调用后，Host 驱动 Client 发起 `tools/call` 请求并等待 Server 返回结果。

---

### 3. 工程取舍与边界
- **协议解耦 vs 性能开销**：传统硬编码工具调用直接在应用进程内执行本地函数；而 MCP 通过 JSON-RPC 跨进程/跨网络序列化传输，每次调用增加约 5ms~30ms 的通信开销。但在企业架构中，这种开销换取了工具生态的极佳复用性与独立更新隔离性。
- **协议不负责流程控制**：MCP 只定义能力接口与通信契约，**绝不负责 Agent 的思考循环与分支编排**。ReAct 循环、状态持久化、审批流依然必须由应用层的 Agent Runtime（如 LangGraph / FastAPI）负责。

---

### 4. 高频追问应对
- **追问 1：MCP 与传统 OpenAI Function Calling 有什么本质区别？**
  - **应对**：Function Calling 只是大模型输出结构化 JSON 的能力定义，工具执行逻辑、鉴权、环境依然硬编码在客户端应用中；MCP 是**统一的客户端-服务端协议标准**。MCP 将工具发现（Discovery）、只读资源挂载（Resources）与工具执行规范化，使一个数据库 MCP Server 能在任意支持 MCP 的平台（Cursor、Claude、自定义 Agent）中即插即用。
- **追问 2：如果 MCP Server 暴露了终端命令行执行（bash）或 SQL 查询能力，如何防范提权？**
  - **应对**：三级防御体系：
    1. **OS 进程级隔离**：Server 必须跑在只读文件系统、无特权用户、受限网络命名空间的 Docker 容器或 WebAssembly 沙箱内；
    2. **Host 层人工审批**：Host 对破坏性操作（如写文件、DROP 表、网络请求）强制弹窗由用户确认；
    3. **参数强校验**：Server 端对命令参数做严格白名单限制，严禁直接拼接 shell 命令字符串。
- **追问 3：在多租户 SaaS 平台中，如何支持远程企业 MCP Server 的安全接入？**
  - **应对**：采用 **SSE/HTTP 传输层 + OAuth2 / API Key 网关校验**。SaaS 平台作为 Host，配置每个租户隔离的 MCP Client 连接实例；对远程 Server 进行双向 TLS（mTLS）加密认证，并通过代理网关实施调用频率限制（Rate Limit）与数据审计日志记录。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿画出 Host、Client、Server 三角关系与调用流程？
- [ ] 能否讲清 Stdio 与 SSE 两种传输协议的适用场景与优劣？
- [ ] 能否阐明 MCP 相比传统硬编码 Function Calling 的生态与架构优势？
