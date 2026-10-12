# 07-project-stories / 项目复盘与技术叙事

## 模块目标
用结构化方式沉淀 10~15 个经得起多轮深挖的高级工程师项目案例。覆盖业务目标、架构决策、难点突破、故障复盘以及过往经历资产转化。

## 案例撰写模版（STAR + 深挖结构）
每个故事独立为一个 markdown 文件（如 `story-01-enterprise-agent.md`），统一采用以下六步框架：
1. **Context & Business Goal**：业务背景、痛点、要解决的核心问题是什么？
2. **Architecture & Decisions**：系统架构图、核心选型权衡（为什么选 A 而不是 B？有哪些妥协？）。
3. **Key Technical Challenge**：最具技术深度的攻坚点（高并发排障、链路中断恢复、评测指标突破等）。
4. **Quantifiable Results**：量化成果（吞吐量提升%、延迟下降ms、测试覆盖率、业务完成率）。
5. **Major Incident & Post-mortem**：线上发生过的最严重故障、定位排查链路、根因分析、后续治理防线。
6. **Retrospective & Improvement**：如果推倒重来，系统会有哪些不同设计？

## 重点准备案例
- [`story-01-enterprise-ai-assistant.md`](file:///Users/mac/workspace/personal/agents/interview-prep/07-project-stories/story-01-enterprise-ai-assistant.md)：核心实战项目（全栈 + Agent 架构）全景复盘（**已就绪**）。
- `story-02-client-to-cloud-continuity.md`：10 年 Android 经验转化案例（复杂状态机、长连接保活、端云协同治理）。
- `story-03-high-concurrency-troubleshooting.md`：Java 后端高并发排障/JVM OOM 排查复盘。
- `story-04-rag-quality-breakthrough.md`：RAG 准确率与多租户隔离优化实战。
