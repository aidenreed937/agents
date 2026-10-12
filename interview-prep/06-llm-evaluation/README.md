# 06-llm-evaluation / 评测、可观测性与安全

## 模块目标
梳理 Agent 应用在生产环境下的质量评估、全链路监控追踪、成本控制策略与安全防护体系。

## 重点课题
1. **评测基准与方法（Evaluation）**
   - 评测维度设计：答案忠实度（Faithfulness）、答案相关性（Answer Relevance）、工具选择准确率、任务完成率
   - 基于 LLM-as-a-Judge 的自动化评测流程构建与人工兜底校准
   - 回归测试集的设计与维护（覆盖边界输入、注入攻击、无解问题）
2. **可观测性（Observability & Tracing）**
   - 链路追踪（Trace）关键事件：Model Call、Tool Execution、Handoff、Guardrail
   - 追踪工具集成与数据模型（如 Langfuse / OpenTelemetry）
   - 延迟剖析（TTFT - Time To First Token 与完整链路耗时分解）
3. **成本与配额控制**
   - Token 消耗统计、模型路由策略（简单任务走小模型，复杂推理走旗舰模型）
   - 提示词缓存（Prompt Caching）与语义缓存应用
4. **安全与防御（Safety & Guardrails）**
   - 提示词注入（Prompt Injection）与间接注入防御手段
   - 敏感信息泄露拦截（PII 脱敏）
   - 工具调用的权限越权防御（强制数据租户隔离）
