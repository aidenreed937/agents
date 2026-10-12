"""Cross-Encoder 精排重排器 (Reranker)
模拟 BGE-Reranker / Cohere Rerank 的交叉注意力打分机制。
对候选集的 Query 与 Chunk 进行深度交叉比对，给出高置信度相关性分数，剔除不相关噪音。
"""
from typing import List, Tuple
from ..models import SearchResult, RerankResult, Chunk
from .bm25 import BM25Retriever


class CrossEncoderReranker:
    """精排交叉重排器"""

    def __init__(self, min_relevance_threshold: float = 0.25, custom_entities: List[str] = None):
        self.min_relevance_threshold = min_relevance_threshold
        default_entities = [
            "502", "429", "waf", "cors", "gb", "ddos", "challenge", "timeout", "flood", "syn", "ssl",
            "billing", "fee", "费用", "计费", "配额", "权限", "rbac", "admin", "viewer",
            # 传统垂直行业（能源电力与工业特种装备）核心实体
            "c2h2", "c2h4", "c2h6", "ch4", "h2", "co", "co2", "总烃", "thc", "乙炔", "乙烯", "甲烷", "氢气",
            "三比值法", "特征气体", "注意值", "放电", "电弧", "局部放电", "火花", "过热", "油纸", "变压器",
            "电抗器", "套管", "互感器", "瓦斯", "继电器", "轻瓦斯", "重瓦斯", "色谱", "pms", "scada"
        ]
        self.domain_entities = default_entities + (custom_entities or [])

    def rerank(self, query: str, candidates: List[SearchResult], top_n: int = 3) -> List[RerankResult]:
        """对候选结果进行逐条交叉精算"""
        query_lower = query.lower()
        query_words = set(BM25Retriever.tokenize(query))

        scored_results: List[RerankResult] = []

        for item in candidates:
            chunk = item.chunk
            al = chunk.action_link
            al_meta = f"{al.console_path} {al.cli_command or ''} {al.required_permission or ''}" if al else ""
            full_searchable_text = f"{chunk.contextualized_content} {al_meta}".lower()
            content_lower = chunk.raw_content.lower()

            # 1. 词面精准命中率 (利用上下文增强与元数据)
            matched_terms = [w for w in query_words if len(w) > 1 and w in full_searchable_text]
            term_overlap_ratio = len(matched_terms) / max(len(query_words), 1)

            # 2. 标题与面包屑路径匹配奖励（结构化上下文红利）
            breadcrumb_bonus = 0.0
            for bc in chunk.breadcrumbs:
                if any(w in bc.lower() for w in query_words if len(w) > 1):
                    breadcrumb_bonus += 0.2
            breadcrumb_bonus = min(breadcrumb_bonus, 0.4)

            # 3. 核心实体与领域参数加权 (覆盖云服务与工业规程两大场景)
            entity_bonus = 0.0
            if any(code in query_lower and code in full_searchable_text for code in self.domain_entities):
                entity_bonus = 0.3

            # 综合计算 Cross-Encoder 模拟分数
            raw_score = (term_overlap_ratio * 0.45) + breadcrumb_bonus + entity_bonus + (item.score * 5.0)
            normalized_score = min(max(raw_score, 0.05), 0.99)
            normalized_score = round(normalized_score, 3)

            rationale = []
            if matched_terms:
                rationale.append(f"命中字面关键词: {matched_terms}")
            if breadcrumb_bonus > 0:
                rationale.append("命中标题/面包屑分类")
            if entity_bonus > 0:
                rationale.append("命中核心参数/错误码标识")

            rationale_str = " | ".join(rationale) if rationale else "语义弱相关"

            if normalized_score >= self.min_relevance_threshold:
                scored_results.append(RerankResult(
                    chunk=chunk,
                    relevance_score=normalized_score,
                    rationale=rationale_str
                ))

        # 按重排分数倒序
        scored_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_results[:top_n]
