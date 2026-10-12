# 面试卡：如何科学评估与观测 Agent 系统？（Evaluation & Tracing）

**模块**：06-llm-evaluation ｜ **难度**：高级 ｜ **熟练度**：A

---

### 1. 30 秒电梯回答
评价 Agent 系统绝不能只看聊天界面的“成功样例截图”，必须建立**“离线基准评测 + 线上全链路可观测（Tracing）”**的闭环体系。
- **离线评测**：用包含 100~300 条典型案例的 Golden Dataset，拆解评估 RAG 三元组（上下文相关性、忠实度、回答相关性）、工具调用准确率以及端到端任务完成率，并将评测分级接入 CI/CD 门禁。
- **在线观测**：基于 OpenTelemetry / Langfuse 建立 Trace/Span 树状调用链，记录各阶段输入输出、TTFT 延迟、Token 消耗与异常，配合人工抽检（Kappa 一致性校验）校准评测模型偏差。

---

### 2. 深入原理
1. **RAG 核心评测指标（RAG Triad）**：
   - **Context Relevance（检索相关性）**：召回切块中包含解题所需信息的比例（评估检索器召回质量）。
   - **Faithfulness（忠实度/真实性）**：模型生成的每一句结论在上下文检索依据中有直接支撑的比例（评估幻觉率）。
   - **Answer Relevance（答案相关性）**：输出是否针对用户原始问题，无答非所问或废话冗余。
2. **Agent 核心评测指标（Agentic Metrics）**：
   - **Tool Calling Accuracy**：工具选型准确率、入参合规率及调用序列最优度。
   - **Task Completion Rate**：多轮复杂任务下最终达到用户明确业务目标的比例。
   - **Trajectory Efficiency**：完成同一目标所消耗的平均步骤数（Steps）与 Token 成本。
3. **Tracing 数据模型（树状 Trace/Span）**：
   - `Trace` 对应单次用户交互会话；下挂多个 `Span`，分别标记 `retrieval`、`model_inference`、`tool_execution`、`guardrail_check`。每个 Span 记录开始/结束时间戳、Payload、Token 统计与状态码。

---

### 3. 工程取舍与边界
- **LLM-as-a-Judge 的偏差治理**：大模型作为裁判存在长度偏好（Verbosity Bias）与自我偏好。不可完全依赖自动化评分，必须引入定期人工抽检（如每周 5% 抽样），计算人工与模型评测的 Kappa 一致性系数。
- **分级回归门禁控制评测成本**：全量跑数百条测试集消耗高昂 API 成本与分钟级时间。工程上采用分级门禁：代码提交 PR 触发 20 条轻量 Smoke Test；夜间离线定时任务执行全量基准回归。

---

### 4. 高频追问应对
- **追问 1：如果业务没有充足的人工标注测试集，如何冷启动建立评测？**
  - **应对**：使用“逆向合成法（Synthetic Data Generation）”。从企业现有知识库文档中利用强推理模型抽取核心知识点，自动逆向生成“模拟问题、检索依据、标准答案”对，经轻量人工剔除后快速沉淀首批 100 条基准集。
- **追问 2：生产线上用户抱怨“回答很慢”，如何利用 Tracing 定位瓶颈？**
  - **应对**：分析 Trace 树分段耗时，重点拆解：① **TTFT（首字延迟）**反映模型排队与 Prefill 计算时延；② **Tool Execution Latency**反映外部工具/SQL/网络 I/O 耗时；③ **Token Generation Throughput**反映逐字解码生成速率（tokens/sec）。
- **追问 3：生产线上 Tracing 记录完整 Prompt 和 Tool 参数是否会导致敏感数据泄漏？**
  - **应对**：必须在 Span 上报前引入数据脱敏管道，对手机号、身份证、密钥等 PII 数据进行正则脱敏或哈希遮蔽；对金融等高敏场景，仅记录 Payload 哈希并在内网受限存储中保存密文。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿说明 RAG 评测三元组（Context Relevance, Faithfulness, Answer Relevance）的具体定义？
- [ ] 能否讲清 Tracing 中 Trace 与 Span 的层级关系及各自记录的核心字段？
- [ ] 能否说明如何用分级门禁策略在 CI/CD 中落地低成本自动化回归评测？
