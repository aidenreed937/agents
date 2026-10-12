# 知识库与控制台 Agent 技术文档体系 (Architecture & Design Docs)

本文档库为 `knowledge_qa_agent` 的深度设计与工程实践白皮书，详细记录了从企业级非标数据治理、结构化解析、Anthropic 上下文增强切片、快慢双轨路由，到动态诊断探针并发编排（Tool-RAG）、多租户物理硬隔离与自动化评测基准的全链路设计细节。

---

## 一、 文档体系结构

```
examples/knowledge_qa_agent/docs/
├── README.md                                    # 本文档：文档库导航与知识体系索引
├── 01_system_architecture.md                    # 全链路系统架构设计与核心生命周期
├── 02_ingestion_and_contextual_retrieval.md     # 数据摄取、AST 解析与上下文增强检索深度实践
├── 03_dual_track_routing_and_tool_rag.md        # 控制台快慢双轨路由与 Orchestrated Tool-RAG 闭环
├── 04_multitenancy_and_rbac_security.md         # 企业级多租户与 RBAC 物理硬隔离架构
└── 05_evaluation_and_complex_stress_benchmarks.md# 质量评测基准、垂直行业验证与高难度场景压测
```

---

## 二、 核心章节导读与速查

| 章节编号与主题 | 核心命题与解决的技术痛点 | 关联核心源码文件 |
| :--- | :--- | :--- |
| [01. 全链路系统架构设计](01_system_architecture.md) | 深入解析天真 RAG 的致命缺陷；阐述端到端分层系统架构、组件交互时序图以及统一契约模型设计。 | `src/models.py`<br>`main.py` |
| [02. 数据摄取与上下文检索](02_ingestion_and_contextual_retrieval.md) | 深入 AST 语法树解析与网页 DOM 去噪；落地 Anthropic 上下文面包屑注入与 Small-to-Big 父子块索引；实现 BM25 + Dense + RRF 混合检索与 Cross-Encoder 交叉重排。 | `src/ingestion/`<br>`src/retrieval/` |
| [03. 双轨路由与 Tool-RAG 闭环](03_dual_track_routing_and_tool_rag.md) | 详解类似 Cloudflare/Google Cloud 的快轨直达（Cmd+K）与慢轨分流；实现多线程池并发动态诊断探针（Orchestrated Parallel Tool-RAG）；构建严格 XML 防幻觉约束与溯源提示词。 | `src/navigation/router.py`<br>`src/agent/` |
| [04. 多租户与 RBAC 安全隔离](04_multitenancy_and_rbac_security.md) | 剖析事后过滤的权限泄露风险；详解物理前置硬过滤（Hard Pre-filtering）机制；探讨 SQLite 原生 FTS5 倒排索引与 Float32 BLOB 向量持久化。 | `src/models.py`<br>`src/storage/sqlite_store.py` |
| [05. 评测基准与高难度场景压测](05_evaluation_and_complex_stress_benchmarks.md) | 介绍离线自动化回归测试基准与 CI 门禁；解读能源电力行业规程（DL/T 722）阶段验证报告；复盘跨规程多跳、计算映射、强干扰抗混淆等极限压力测试。 | `eval_benchmark.py`<br>`verify_industrial.py`<br>`verify_complex_stress.py` |

---

## 三、 推荐阅读路径

1. **架构师 / 全貌了解者**：建议先阅读 [01_system_architecture.md](01_system_architecture.md)，掌握整体快慢双轨和并发双路召回的宏观设计，再阅读 [04_multitenancy_and_rbac_security.md](04_multitenancy_and_rbac_security.md) 理解安全边界。
2. **搜索与算法工程师**：重点研读 [02_ingestion_and_contextual_retrieval.md](02_ingestion_and_contextual_retrieval.md) 和 [05_evaluation_and_complex_stress_benchmarks.md](05_evaluation_and_complex_stress_benchmarks.md)，掌握面包屑注入、RRF 融合与基于指标的精细调优。
3. **Agent / 工程落地开发者**：重点研读 [03_dual_track_routing_and_tool_rag.md](03_dual_track_routing_and_tool_rag.md)，理解如何将静态手册 RAG 与底层监控探针结合实现自动化故障确诊与操作直达。
