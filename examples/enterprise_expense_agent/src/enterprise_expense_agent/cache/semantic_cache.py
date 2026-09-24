"""Layer 2: 流量与效率层 - 语义缓存引擎 (Semantic Cache)
在查询大模型前，基于轻量语义相似度算法与关键词特征快速判断历史相似度。
若语义相似度超过阈值，直接返回缓存结果，达到 0 Token 消耗与毫秒级即时响应。
"""
import difflib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class CacheEntry:
    """缓存条目"""
    query: str
    result: Any
    created_at: float
    token_cost: int
    hit_count: int = 0

@dataclass
class CacheStats:
    """缓存命中与效益统计"""
    hits: int = 0
    misses: int = 0
    saved_tokens: int = 0
    saved_latency_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0

class SemanticCache:
    """轻量零依赖语义缓存器"""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self._cache: List[CacheEntry] = []
        self.stats = CacheStats()

    def _normalize_text(self, text: str) -> str:
        """清洗归一化文本标点与空格"""
        chars_to_remove = set(" ，。！？,!? \t\n\r")
        return "".join(c.lower() for c in text if c not in chars_to_remove)

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """
        利用 SequenceMatcher 计算字符层级的语义相近度 (0.0 ~ 1.0)
        """
        norm1 = self._normalize_text(query1)
        norm2 = self._normalize_text(query2)
        if norm1 == norm2:
            return 1.0
        matcher = difflib.SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()

    def get(self, query: str) -> Optional[Tuple[Any, float]]:
        """
        查询语义缓存
        返回: (缓存结果, 匹配相似度) 或 None
        """
        start_time = time.perf_counter()
        best_match: Optional[CacheEntry] = None
        highest_sim = 0.0

        for entry in self._cache:
            sim = self._calculate_similarity(query, entry.query)
            if sim > highest_sim:
                highest_sim = sim
                best_match = entry

        if best_match and highest_sim >= self.threshold:
            best_match.hit_count += 1
            self.stats.hits += 1
            self.stats.saved_tokens += best_match.token_cost
            # 假设 LLM 典型网络响应需要 800ms
            self.stats.saved_latency_ms += 800.0
            return best_match.result, highest_sim

        self.stats.misses += 1
        return None

    def set(self, query: str, result: Any, token_cost: int = 350) -> None:
        """
        写入语义缓存
        """
        # 如果已存在极高相似的，更新已有条目
        for entry in self._cache:
            if self._calculate_similarity(query, entry.query) >= 0.98:
                entry.result = result
                entry.token_cost = token_cost
                return

        self._cache.append(
            CacheEntry(
                query=query,
                result=result,
                created_at=time.time(),
                token_cost=token_cost,
            )
        )

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self.stats = CacheStats()
