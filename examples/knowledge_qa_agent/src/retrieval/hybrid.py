"""混合检索器 (Hybrid Retriever with Reciprocal Rank Fusion - RRF)
同时并发执行【字面关键词粗筛】与【语义向量粗筛】，通过 RRF 算法无偏融合两路排名。
"""
from typing import List, Dict, Optional
from ..models import Chunk, SearchResult, UserContext
from .bm25 import BM25Retriever
from .dense import DenseSemanticRetriever


class HybridRRFRetriever:
    """生产级混合检索融合器"""

    def __init__(self, bm25: BM25Retriever, dense: DenseSemanticRetriever, rrf_k: int = 60):
        self.bm25 = bm25
        self.dense = dense
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 10,
        candidate_pool: int = 20,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """执行双路召回并用 RRF 公式归一化排名融合 (支持多租户与 RBAC 权限硬隔离)"""
        bm25_results = self.bm25.search(query, top_k=candidate_pool, user_context=user_context)
        dense_results = self.dense.search(query, top_k=candidate_pool, user_context=user_context)

        # RRF 打分字典: chunk_id -> 累计 RRF 分数
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        # 1. 累加 BM25 排名得分
        for item in bm25_results:
            if item.score <= 0.0:
                continue
            cid = item.chunk.chunk_id
            chunk_map[cid] = item.chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + item.rank))

        # 2. 累加 向量 排名得分
        for item in dense_results:
            if item.score <= 0.0:
                continue
            cid = item.chunk.chunk_id
            chunk_map[cid] = item.chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + item.rank))

        # 3. 按综合 RRF 分数从高到低排序
        sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        results: List[SearchResult] = []
        rank = 1
        for cid in sorted_cids[:top_k]:
            results.append(SearchResult(
                chunk=chunk_map[cid],
                score=round(rrf_scores[cid], 5),
                rank=rank,
                source_type="rrf_hybrid"
            ))
            rank += 1

        return results
