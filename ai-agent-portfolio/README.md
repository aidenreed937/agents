# AI Agent 工程作品集

三个递进的 AI Agent 工程项目:从检索增强(RAG)到自主编排(Agent),再到研发提效工具。三者共享同一套技术底座、层层复用——作品一的规范知识库为作品三的代码 Review 提供检索能力,作品二的编排与工具层贯穿全程。

## 技术底座

- **语言**:Python 3.12(`uv` 管理虚拟环境)
- **LLM**:GLM-4.7-Flash(OpenAI 兼容 API)/ 本地 Ollama `qwen2.5:7b` 兜底
- **Embedding**:本地 `bge-m3`
- **向量库**:PostgreSQL + pgvector(`langchain-postgres` + `psycopg3`)
- **RAG**:LangChain
- **Rerank**:`bge-reranker`(API)
- **Agent 编排**:LangGraph
- **Web UI**:Streamlit

## 项目

| 项目 | 说明 | 状态 |
|---|---|---|
| [project-1-rag](project-1-rag/) | 全栈工程规范知识库问答(RAG + rerank + 引用溯源 + 评估) | 规划中 |
| [project-2-agent](project-2-agent/) | 自主规划业务 Agent(LangGraph 编排 + 权限控制 + Human-in-the-Loop) | 规划中 |
| [project-3-coding](project-3-coding/) | 全栈代码 Review Agent(复用 project-1 规范库 + project-2 编排) | 规划中 |

每个项目目录内含独立 README:背景、架构、技术选型理由、量化指标与运行方式。

## 工程关注点

- 接口抽象、状态机、容错降级、权限控制、并发调度
- 危险操作的 Human-in-the-Loop 拦截
- 检索质量的量化评估(召回率、Top-K 命中率)
