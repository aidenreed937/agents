# 08-interview-cards / 可打印面试卡

## 模块目标
存放高度凝练、适合 A4 打印的闭卷口述练习卡片。每张卡片对应一个高频核心问题，严格控制在单页篇幅，专注口述逻辑与应对深挖。

## 卡片命名规范
`card-[模块编号]-[序号]-[主题简述].md`
例如：
- `card-01-01-jvm-oom-troubleshooting.md`
- `card-03-01-pgvector-vs-dedicated-vector-db.md`
- `card-05-01-agent-tool-calling-failure.md`

## 单卡标准模板
```markdown
# [问题题目]

**模块**：[所属模块] ｜ **难度**：[中级 / 高级] ｜ **熟练度**：[A / B / C]

### 1. 30 秒电梯回答
[核心论点、本质机制、一句话结论]

### 2. 深入原理
[底层机制、流程流转、关键数据结构或协议规范]

### 3. 工程取舍与边界
[什么情况下适用？什么情况下不适用？有哪些风险与代价？]

### 4. 高频追问应对
- 追问 1：...
  - 核心逻辑：...
- 追问 2：...
  - 核心逻辑：...
- 追问 3：...
  - 核心逻辑：...

### 5. 90 秒自测标准
- [ ] 能否闭卷脱稿完整讲述核心机制？
- [ ] 能否清晰解释故障或边界场景的应对策略？
- [ ] 是否在 90 秒内完成，无多余虚词与卡顿？
```

## 已就绪 P0 面试卡清单
| 卡号 | 主题 | 模块 | 核心考核点 |
| :--- | :--- | :--- | :--- |
| [`card-00-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-00-01-llm-fundamentals-sampling-tokenizer.md) | 大模型核心基础：解码采样 (Temp/Top-P) 与 Token 分词 | 00-foundations | Softmax 温度数学机制、Prefill/Decoding 瓶颈、JSON 工具调用温度锁死 |
| [`card-01-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-01-01-jvm-high-cpu-oom-troubleshooting.md) | 生产环境 CPU 100% 与 OOM 排障全链路 | 01-java-backend | 现场止血、四步排查命令链、堆外内存与容器感知 |
| [`card-02-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-02-01-sse-streaming-reconnection.md) | Web/客户端到 LLM 的 SSE 流式中断如何恢复？ | 02-web-fullstack | 任务解耦、Last-Event-ID 补发机制、异步长连接与心跳 |
| [`card-03-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-03-01-pgvector-vs-dedicated-vector-db.md) | RAG 向量存储选型：pgvector 与专有向量库的权衡 | 03-database-system | 单库 ACID 优势、HNSW/IVFFlat 权衡、多租户行级隔离 (RLS) |
| [`card-05-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-05-01-agent-tool-calling-failure.md) | Agent 工具调用失败怎么处理？ | 05-agent-engineering | 错误四分类、自纠错机制、幂等键设计、死循环防护 |
| [`card-05-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-05-02-human-in-the-loop-state-machine.md) | Agent 状态持久化与 Human-in-the-loop 人工审批 | 05-agent-engineering | Checkpoint 断点快照、状态机挂起/唤醒、高危拦截与参数防篡改 |
| [`card-06-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-06-01-agent-evaluation-and-tracing.md) | 如何科学评估与观测 Agent 系统？ | 06-llm-evaluation | RAG 三元组、任务完成率、全链路 Tracing、CI 回归与防御 |
| [`card-02-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-02-02-react-hooks-closure-render-optimization.md) | React Hooks 闭包陷阱与流式打字机渲染优化 | 02-web-fullstack | 闭包陷阱根因与解法、requestAnimationFrame 节流缓冲、动态虚拟滚动 |
| [`card-03-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-03-02-redis-cache-consistency-distributed-lock.md) | Redis 双写一致性与分布式锁正确落地 | 03-database-system | 先更库再删缓存、Lua 原子防误删、Watchdog 续期、Fencing Token |
| [`card-05-03`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-05-03-rag-hybrid-search-and-reranking.md) | RAG 检索优化：混合检索与重排 (Rerank) | 05-agent-engineering | BM25 + 向量双路召回、RRF 排名融合、Cross-Encoder 交叉重排、Small-to-Big |
| [`card-01-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-01-02-spring-transaction-pitfalls-and-propagation.md) | Spring 声明式事务失效根因与分布式业务幂等设计 | 01-java-backend | AOP 代理自调用失效、传播行为与保存点、禁止外部大模型长事务、三道防线幂等 |
| [`card-04-01`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-04-01-llm-rate-limiting-and-cost-budgeting.md) | 高并发 LLM 网关限流 (RPM/TPM) 与调度系统设计 | 04-system-design | RPM+TPM 双维度令牌桶、两阶段预扣结算、多供应商 Fallback、租户公平配额与硬熔断 |
| [`card-05-04`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-05-04-mcp-protocol-architecture-and-security.md) | MCP 协议架构剖析与企业级安全沙箱隔离 | 05-agent-engineering | Host/Client/Server 角色模型、Stdio vs SSE 传输层、工具发现与物理执行沙箱 |
| [`card-06-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-06-02-prompt-injection-and-guardrails-defense.md) | 提示词注入 (Prompt Injection) 与安全 Guardrails 防御体系 | 06-llm-evaluation | 直接 vs 间接注入、XML 数据定界、执行权限解耦、输出金丝雀标记与 PII 脱敏 |
| [`card-03-03`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-03-03-postgresql-slow-query-execution-plan-tuning.md) | PostgreSQL 慢查询定位与 Explain Analyze 调优 | 03-database-system | Cost 与真实耗时偏差诊断、三种扫描算法取舍、work_mem 磁盘溢出、深度分页优化 |
| [`card-01-03`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-01-03-java-concurrency-jmm-threadpool-tuning.md) | Java JMM、volatile 屏障与线程池生产调优 | 01-java-backend | MESI 缓存一致性、lock 指令内存屏障、DCL 半初始化防范、I/O 密集型参数与 CallerRunsPolicy |
| [`card-02-03`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-02-03-modern-auth-jwt-refresh-token-rbac.md) | 现代 Web 认证：双令牌无感刷新与 RBAC 权限设计 | 02-web-fullstack | Refresh Token 轮转与重放撤销、Axios 响应拦截并发队列、水平越权数据隔离 |
| [`card-04-02`](file:///Users/mac/workspace/personal/agents/interview-prep/08-interview-cards/card-04-02-applied-algorithms-and-tuning.md) | 工程算法与数据结构选型及性能调优（缓存·ANN·限流·匹配） | 04-system-design | W-TinyLFU 频次衰减、HNSW 参数与 PQ 压缩、RRF 非参数化排名融合、惰性双维令牌桶、AC 自动机与双数组压缩 |
