# 04-system-design / 系统设计与可靠性工程

## 模块目标
梳理高级工程师必备的系统设计分析框架、高并发与可靠性设计模式、以及 AI Agent 系统特有的架构模式。

## 重点课题
1. **系统设计通用方法论**
   - 需求拆解与边界澄清（功能需求、非功能需求）
   - 容量预估计算模版（QPS、并发量、网络带宽、存储容量计算）
   - 数据模型与 API 契约定义
2. **高可用与容错机制**
   - 幂等性设计（客户端请求 ID、Token 机制、数据库唯一约束）
   - 限流算法（令牌桶、漏桶、滑动窗口）与降级熔断策略
   - 分布式事务与最终一致性模式（Saga 模式、本地消息表）
3. **AI / Agent 专项系统架构**
   - 长耗时异步任务的架构设计（轮询 vs WebSocket vs SSE）
   - 高并发场景下的 LLM Rate Limit（并发配额、RPM/TPM 控制与排队调度）
   - 端云协同架构（客户端状态机、本地离线与云端 AI 协同模型）
4. **核心工程算法与系统调优**
   - [`algorithms-in-engineering.md`](file:///Users/mac/workspace/personal/agents/interview-prep/04-system-design/algorithms-in-engineering.md)：W-TinyLFU 缓存淘汰、HNSW/IVFFlat 向量近似检索参数调优、RRF 与两阶段级联重排、双维度惰性令牌桶、AC 自动机与双数组压缩。
