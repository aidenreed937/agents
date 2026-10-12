"""稠密语义检索器体系 (Dense Semantic Vector Retriever)
支持两种运行模式：
1. FastEmbedDenseRetriever: 基于 fastembed + ONNX Runtime 的工业级真实深度学习向量检索
   (默认使用 BAAI/bge-small-zh-v1.5 模型，纯 CPU 高性能并行计算，告别 PyTorch 臃肿)；
2. SimulatedDenseRetriever: 基于纯 Python 空间投影的零依赖模拟实现 (用于环境未安装依赖时的保底降级)；
3. DenseSemanticRetriever: 统一门面与策略路由器，自动探测环境并实施优雅降级。
"""
from abc import ABC, abstractmethod
import math
import hashlib
from typing import List, Dict, Optional
from ..models import Chunk, SearchResult, UserContext


class BaseVectorRetriever(ABC):
    """向量检索适配器统一契约 (Target Interface)"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        pass

    @property
    @abstractmethod
    def embeddings(self) -> List[List[float]]:
        """已索引的切片向量矩阵"""
        pass

    @abstractmethod
    def fit(self, chunks: List[Chunk]):
        """离线建立向量索引"""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 10, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        """在线计算查询向量并返回最近邻切片 (支持多租户与 RBAC 权限硬隔离)"""
        pass


class FastEmbedDenseRetriever(BaseVectorRetriever):
    """适配器 1: 工业级轻量向量引擎 (基于 fastembed + ONNX Runtime)
    无需显卡与庞大的 PyTorch 环境，利用 ONNX C++ 多线程在纯 CPU 上毫秒级推理真实 512 维特征投影。
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise RuntimeError(
                "未检测到 fastembed 依赖，请在终端执行: pip install fastembed"
            )
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name)
        self.chunks: List[Chunk] = []
        self._embeddings: List[List[float]] = []

    @property
    def dimension(self) -> int:
        return 512

    @property
    def embeddings(self) -> List[List[float]]:
        return self._embeddings

    def fit(self, chunks: List[Chunk]):
        self.chunks = chunks
        texts = [c.contextualized_content for c in chunks]
        # fastembed.embed 返回已归一化的生成器
        emb_gen = self.model.embed(texts)
        self._embeddings = [e.tolist() for e in emb_gen]

    def search(self, query: str, top_k: int = 10, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        q_emb = list(self.model.embed([query]))[0].tolist()
        scores: List[float] = []

        for c_vec in self._embeddings:
            # fastembed 输出已是单位超球面向量，点积即严格余弦相似度
            sim = sum(q * c for q, c in zip(q_emb, c_vec))
            scores.append(sim)

        ranked_indices = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)

        results: List[SearchResult] = []
        rank = 1
        for idx in ranked_indices:
            chunk = self.chunks[idx]

            # 多租户与 RBAC 前置过滤
            if user_context is not None:
                if chunk.tenant_id != "public" and chunk.tenant_id != user_context.tenant_id:
                    continue
                if not user_context.has_permission(chunk.required_permission):
                    continue

            results.append(SearchResult(
                chunk=chunk,
                score=round(scores[idx], 4),
                rank=rank,
                source_type="dense_vector"
            ))
            rank += 1
            if len(results) >= top_k:
                break
        return results


class SimulatedDenseRetriever(BaseVectorRetriever):
    """适配器 2: 纯 Python 启发式模拟向量检索器 (内置零依赖保底策略)
    采用 64 维空间投影与 L2 范数归一化，用于无外部包环境下的自洽演示。
    """

    DIMENSION = 64

    SEMANTIC_CLUSTERS = {
        "network_security": ["安全", "防护", "拦截", "攻击", "恶意", "阻断", "防范", "waf", "防火墙", "人机", "验证码", "ddos"],
        "error_troubleshoot": ["报错", "错误", "故障", "异常", "挂了", "排查", "超时", "失效", "宕机", "无法访问", "502", "429"],
        "cors_headers": ["跨域", "同源", "响应头", "header", "cors", "origin", "凭证", "前后端分离"],
        "billing_cost": ["费用", "计费", "花销", "多少钱", "账单", "扣款", "价格", "超额", "流量费", "折扣", "成本"],
        "traffic_control": ["限流", "速率", "阈值", "并发", "频次", "白名单", "放行", "防刷"],
        "origin_server": ["源站", "后端", "上游", "服务器", "nginx", "apache", "进程", "证书", "ssl"],
        "transformer_dga": ["三比值", "三比值法", "特征气体", "产气", "总烃", "乙炔", "乙烯", "甲烷", "氢气", "色谱", "编码", "改良三比值", "过热", "放电", "电弧"],
        "insulation_test": ["绝缘", "预防性试验", "介损", "吸收比", "极化指数", "击穿电压", "绝缘纸", "受潮", "老化"],
        "equipment_limits": ["注意值", "限值", "基线", "互感器", "套管", "电抗器", "台账"],
        "protective_relay": ["瓦斯", "轻瓦斯", "重瓦斯", "继电器", "跳闸", "报警", "放气", "缺陷"]
    }

    def __init__(self):
        self.chunks: List[Chunk] = []
        self._embeddings: List[List[float]] = []

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    @property
    def embeddings(self) -> List[List[float]]:
        return self._embeddings

    def _text_to_dense_vector(self, text: str) -> List[float]:
        vec = [0.0] * self.DIMENSION
        text_lower = text.lower()

        for cluster_idx, (cluster_name, keywords) in enumerate(self.SEMANTIC_CLUSTERS.items()):
            weight = 0.0
            for kw in keywords:
                if kw in text_lower:
                    weight += 1.5
            dim_start = (cluster_idx * 8) % self.DIMENSION
            for d in range(8):
                vec[(dim_start + d) % self.DIMENSION] += weight * math.cos(d + 1)

        words = text_lower.split()
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.DIMENSION
            sign = 1.0 if ((h >> 4) % 2 == 0) else -1.0
            vec[idx] += sign * 0.5

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 1e-9:
            vec = [v / norm for v in vec]
        return vec

    def fit(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._embeddings = []
        for chunk in chunks:
            v = self._text_to_dense_vector(chunk.contextualized_content)
            self._embeddings.append(v)

    def search(self, query: str, top_k: int = 10, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        q_vec = self._text_to_dense_vector(query)
        scores: List[float] = []

        for c_vec in self._embeddings:
            sim = sum(q * c for q, c in zip(q_vec, c_vec))
            scores.append(sim)

        ranked_indices = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)

        results: List[SearchResult] = []
        rank = 1
        for idx in ranked_indices:
            chunk = self.chunks[idx]

            # 多租户与 RBAC 前置过滤
            if user_context is not None:
                if chunk.tenant_id != "public" and chunk.tenant_id != user_context.tenant_id:
                    continue
                if not user_context.has_permission(chunk.required_permission):
                    continue

            results.append(SearchResult(
                chunk=chunk,
                score=round(scores[idx], 4),
                rank=rank,
                source_type="dense_vector"
            ))
            rank += 1
            if len(results) >= top_k:
                break
        return results


class DenseSemanticRetriever(BaseVectorRetriever):
    """门面与策略路由器 (Facade & Strategy Router)
    对外统一暴露调用入口，支持按需指定底层引擎，或自动探测 fastembed 实现无缝升级与优雅降级。
    """

    def __init__(self, adapter: Optional[BaseVectorRetriever] = None):
        if adapter is not None:
            self.adapter = adapter
        else:
            self.adapter = self._auto_select_adapter()

    @staticmethod
    def _auto_select_adapter() -> BaseVectorRetriever:
        try:
            import fastembed
            return FastEmbedDenseRetriever()
        except Exception:
            return SimulatedDenseRetriever()

    @property
    def current_strategy_name(self) -> str:
        return self.adapter.__class__.__name__

    @property
    def is_real_onnx_model(self) -> bool:
        return isinstance(self.adapter, FastEmbedDenseRetriever)

    @property
    def dimension(self) -> int:
        return self.adapter.dimension

    @property
    def embeddings(self) -> List[List[float]]:
        return self.adapter.embeddings

    def fit(self, chunks: List[Chunk]):
        return self.adapter.fit(chunks)

    def search(self, query: str, top_k: int = 10, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        return self.adapter.search(query, top_k=top_k, user_context=user_context)
