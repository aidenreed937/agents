# Interview Prep 知识库

## 知识库定位与原则
本知识库用于支持从“资深客户端/Java工程师”向“全栈业务 + Agent应用工程师”的转型求职。
核心原则：
1. **单一事实来源**：每个知识点只保留一个主分析文件，不进行多处冗余复制。
2. **三层信息分级**：
   - **知识地图**：宏观脉络，梳理技术点之间的因果与调用关系（存放在各模块根目录或 00-roadmap）。
   - **深入笔记与实战册**：详细原理、源码剖析、故障排查与接口契约（存放在 01~07 模块）。
   - **可打印面试卡**：高度凝练的 90 秒口述版本，包含结论、边界与高频追问（集中存放在 08-interview-cards）。
3. **面试与证据导向**：重点记录“技术选型权衡”、“极端失败场景应对”、“真实排障过程”，而非概念背诵。

## 目录索引
- `00-roadmap/`：目标岗位画像、能力矩阵映射、时间线规划与周计划。
- `01-java-backend/`：Java 核心并发、JVM 调优排障、Spring Boot 机制与企业级事务。
- `02-web-fullstack/`：React 核心与渲染优化、TypeScript 类型系统、HTTP/SSE 流式协议、鉴权机制。
- `03-database-system/`：PostgreSQL / 事务隔离、索引优化、pgvector 向量检索、缓存一致性与幂等。
- `04-system-design/`：系统设计方法论、高可用/容灾、长连接/流式架构、端云协同系统。
- `05-agent-engineering/`：ReAct 循环、Tool Calling 协议、RAG 链路、状态机持久化、HITL 审批、MCP。
- `06-llm-evaluation/`：Agent 评测指标（质量/召回/成本）、Tracing 可观测性、安全注入防御、Guardrails。
- `07-project-stories/`：主打项目复盘（STAR）、历史 Android 资产转化叙事、关键技术选型与重大故障复盘。
- `08-interview-cards/`：符合 A4 打印规格的速记卡，用于闭卷口述练习与艾宾浩斯复习。
- `09-mock-interviews/`：模拟面试记录、真实面试录音/复盘笔记、薄弱卡点追踪。
- `10-application-log/`：公司投递跟踪表、岗位 JD 核心关键词匹配、各轮次反馈与应对策略。

---

## 一键自动化构建 A4 打印手册
知识库内置了自动化编译导出脚本 [`generate_handbook.py`](file:///Users/mac/workspace/personal/agents/interview-prep/generate_handbook.py)，能够自动扫描全量卡片、叙事与项目复盘，生成高质量排版的单文件 HTML 与 PDF。

### 常用命令
```bash
# 执行编译并覆盖更新 PDF 与 HTML
python3 interview-prep/generate_handbook.py
```

### 生成产物
- **PDF 手册**：[`interview-prep/interview-handbook.pdf`](file:///Users/mac/workspace/personal/agents/interview-prep/interview-handbook.pdf)（排版严谨、每张面试卡严格独占一页 A4，可直接外发打印或导入 iPad 翻阅）；
- **HTML 预览**：[`interview-prep/interview-handbook.html`](file:///Users/mac/workspace/personal/agents/interview-prep/interview-handbook.html)（可在任意浏览器中双击直接预览，支持浏览器内 Command+P 自定义打印）。
