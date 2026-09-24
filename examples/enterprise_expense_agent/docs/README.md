# 企业级差旅报销受控智能体（Enterprise Expense Agent）工程设计与架构文档

> **项目定位**：本模块是一个面向企业复杂业务场景、深度集成 **LangGraph** 运行时底座的受控智能体（Controlled Agent）工业级落地参考实现。
> 核心目标是彻底解决大模型在企业落地中的“流程失控”、“状态丢失”、“幻觉脑补”、“越权调用”与“重复建单”等关键工程痛点。

---

## 一、 文档目录导航

| 序号 | 文档名称 | 核心主题与关注点 |
| :--- | :--- | :--- |
| **01** | [01_system_architecture.md](01_system_architecture.md) | **系统架构与 LangGraph 运行时编排**<br/>• 为什么企业受控业务必须选择 LangGraph<br/>• 核心状态图拓扑、节点划分与条件边设计<br/>• 不可变权威事实契约（`ValidatedExpenseClaim`）与版本哈希指纹 |
| **02** | [02_hitl_and_durable_execution.md](02_hitl_and_durable_execution.md) | **人在回路 (HITL) 与持久化冷启动恢复**<br/>• LangGraph 原生 `interrupt()` 与 `Command(resume=...)` 机制<br/>• `LangGraphFileCheckpointer` 双轨持久化引擎设计<br/>• 模拟 Worker 进程崩溃后的冷启动现场重建与防篡改验签 |
| **03** | [03_security_governance_and_idempotency.md](03_security_governance_and_idempotency.md) | **零信任安全、数据中台核验与两阶段幂等**<br/>• 零信任 RBAC 与 `SecurityContext` 会话凭据<br/>• Layer 1 防护网：PII 敏感脱敏与防注入防火墙<br/>• 三方数据事实交叉核验与两阶段防重入账机制 |
| **04** | [04_evaluation_and_benchmark.md](04_evaluation_and_benchmark.md) | **评测驱动开发 (EDD) 与测试基准套件**<br/>• 涵盖 9 大业务维度的 20 组真实黄金测试集<br/>• 自动化评估指标体系与基准运行器（Benchmark Runner）<br/>• 单元回归测试与本地隔离虚拟环境操作指南 |

---

## 二、 核心技术栈与架构规范

- **编排运行时（Orchestration Runtime）**：LangGraph 1.2+ 原生 `StateGraph`，声明式控制节点跃迁与外部规则路由；
- **基础执行环境**：Python 3.12+ / 3.14+，推荐使用 `uv` 搭建项目本地隔离虚拟环境；
- **状态持久化引擎（Checkpointer）**：实现 LangGraph `BaseCheckpointSaver` 规范的 `LangGraphFileCheckpointer`，支持全量通道版本管理与跨进程崩溃恢复；
- **工具协议标准**：提供基于 JSON-RPC 2.0 的标准 MCP Server 实现（[mcp/expense_mcp_server.py](../mcp/expense_mcp_server.py)）；
- **治理与安全底座**：零信任上下文安全凭据（`SecurityContext`）、Prompt 安全防火墙（`PromptGuardrail`）、两阶段幂等管理器（`IdempotencyManager`）。

---

## 三、 代码关键位置索引

- 全局状态定义：`examples/enterprise_expense_agent/src/enterprise_expense_agent/agent/state.py:13`
- 不可变业务契约：`examples/enterprise_expense_agent/src/enterprise_expense_agent/agent/schema.py:46`
- LangGraph 状态图与调度：`examples/enterprise_expense_agent/src/enterprise_expense_agent/agent/workflow.py:24`
- LangGraph 原生检查点：`examples/enterprise_expense_agent/src/enterprise_expense_agent/agent/checkpointer.py:34`
- 零信任安全凭证与 RBAC：`examples/enterprise_expense_agent/src/enterprise_expense_agent/governance/rbac.py:17`
- 人在回路特批协同引擎：`examples/enterprise_expense_agent/src/enterprise_expense_agent/governance/hitl.py:33`
- 两阶段业务幂等引擎：`examples/enterprise_expense_agent/src/enterprise_expense_agent/governance/idempotency.py:11`
- 标准 MCP 工具服务：`examples/enterprise_expense_agent/src/enterprise_expense_agent/mcp/expense_mcp_server.py:17`
