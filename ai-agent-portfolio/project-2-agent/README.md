# 作品二:自主规划业务 Agent(LangGraph)

数据库运维 Agent(带误删防护)——LangGraph 编排的多步自主 Agent,危险操作经 Human-in-the-Loop 拦截。

## 技术栈

LangGraph(State / Node / Edge + 持久化 + HITL) + 作品一 RAG + 自写 Tool Registry + GLM + Streamlit

## 核心流程

规划 → 工具调用 → 反思 → 输出

## 工程亮点

- 权限控制 + HITL:危险操作前强制人工确认
- 终止三件套:最大步数 + 重复动作检测 + 参数去重
- 容错降级:工具失败重试、超时降级、状态持久化
- 并发调度

## 量化指标(待实测填入)

- 工具调用成功率:—
- 危险操作 HITL 拦截率:—
- 平均响应时长:—

## 运行

> 待补:环境准备、启动命令、demo 截图 / 链接

---

> 状态:规划中
