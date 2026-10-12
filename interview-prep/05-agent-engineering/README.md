# 05-agent-engineering / Agent 应用工程

## 模块目标
梳理 AI Agent 生产落地的核心工程能力，涵盖工具调用、RAG 检索管道、状态管理与持久化、人机协作审批及协议规范。

## 重点课题
1. **模型调用与 ReAct 运行循环**
   - 原生 ReAct 状态循环手写实现与关键边界
   - Function Calling / Tool Calling 协议规范与 JSON Schema 参数校验
   - 工具执行失败与超时的错误分类与容错重试策略
2. **RAG 检索管道构建**
   - 文档解析与 Chunking 策略（递归字符切分、语义切分）
   - 混合检索（Keyword / BM25 + Dense Vector）与重排（Rerank）
   - 引用溯源与防幻觉机制
3. **Agent 状态管理与持久化**
   - 对话上下文窗口（Context Window）剪枝与摘要压缩
   - 短期工作流状态 vs 长期用户画像记忆
   - 状态持久化机制（Checkpointer 实现断点保存与故障恢复）
4. **控制流与 Human-in-the-loop**
   - 确定性工作流（DAG）与自主 Agent 的边界划分
   - 敏感操作（写入/删除/支付）的人工审批中断与唤醒流程
5. **模型上下文协议（MCP）**
   - Host、Client、Server 三角色职责划分
   - 工具发现、协议传输与外部权限隔离模型
