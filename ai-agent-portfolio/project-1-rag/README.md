# 作品一:企业级知识库问答系统(RAG)

全栈工程规范知识库问答——后端 Python/API 规范 + 前端 React/TS 规范合一,带引用溯源、rerank 与检索评估。

## 技术栈

`langchain-postgres`(pgvector) + 本地 `bge-m3` embedding + GLM 生成 + `bge-reranker`(API) + Streamlit

## 核心链路

文档加载 → chunking → embedding → pgvector → 检索 → rerank → 拼 prompt → 带引用生成

## 工程亮点

- 检索为空的兜底回答
- LLM 超时重试
- 并发查询调度

## 量化指标(待实测填入)

- Top-3 命中率(rerank 前 → 后):— → —
- 引用溯源覆盖率:—
- 评估测试集规模:— 条

## 运行

> 待补:环境准备、`uv sync`、启动命令、demo 截图 / 链接

---

> 状态:规划中
