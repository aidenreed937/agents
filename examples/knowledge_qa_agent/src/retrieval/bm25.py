"""稀疏关键词检索器 (BM25 Okapi 实现)
擅长精确匹配专有名词、错误码、路由路径、参数名。
"""
import math
import re
from typing import List, Dict, Set, Optional
from ..models import Chunk, SearchResult, UserContext


class BM25Retriever:
    """生产级 BM25 Okapi 稀疏检索算法"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[Chunk] = []
        self.doc_len: List[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.term_freqs: List[Dict[str, int]] = []
        self.corpus_size: int = 0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """中英文分词器：提取英文标识符/代码/子词，并对中文生成 2-gram 与词块"""
        text = text.lower()
        tokens: List[str] = []

        # 1. 提取连续英文、数字、下划线、短横线、点号（如 ERR_GATEWAY_502, Access-Control-Allow-Origin）
        code_words = re.findall(r'[a-z0-9_\-\./]+', text)
        for w in code_words:
            if len(w) > 1:
                tokens.append(w)
                # 将复合标识符（如 err_gateway_502）拆出子单元（502, gateway, err）增强召回
                subparts = re.split(r'[_\-\./]+', w)
                if len(subparts) > 1:
                    tokens.extend([sp for sp in subparts if len(sp) > 1])

        # 2. 提取中文字符串并建立词块与 2-gram
        chinese_blocks = re.findall(r'[\u4e00-\u9fa5]+', text)
        for block in chinese_blocks:
            if len(block) == 1:
                tokens.append(block)
            else:
                for i in range(len(block) - 1):
                    tokens.append(block[i:i+2])
                if 2 < len(block) <= 4:
                    tokens.append(block)

        return tokens

    def fit(self, chunks: List[Chunk]):
        """离线构建 BM25 倒排索引表"""
        self.chunks = chunks
        self.corpus_size = len(chunks)
        self.doc_len = []
        self.term_freqs = []
        self.doc_freqs = {}

        total_len = 0
        for chunk in chunks:
            # 使用带有上下文面包屑的文本建索
            tokens = self.tokenize(chunk.contextualized_content)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)

            tf: Dict[str, int] = {}
            seen: Set[str] = set()
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                seen.add(t)
            self.term_freqs.append(tf)

            for t in seen:
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avg_doc_len = (total_len / self.corpus_size) if self.corpus_size > 0 else 0.0

    def search(self, query: str, top_k: int = 10, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        """根据 Query 计算 BM25 得分并返回 Top-K 召回列表 (支持多租户与 RBAC 权限物理硬隔离)"""
        query_tokens = self.tokenize(query)
        scores: List[float] = [0.0] * self.corpus_size

        for token in query_tokens:
            if token not in self.doc_freqs:
                continue

            # 计算 IDF
            df = self.doc_freqs[token]
            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

            for idx in range(self.corpus_size):
                tf = self.term_freqs[idx].get(token, 0)
                if tf == 0:
                    continue
                d_len = self.doc_len[idx]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (d_len / self.avg_doc_len))
                scores[idx] += idf * (numerator / denominator)

        # 排序
        ranked_indices = sorted(range(self.corpus_size), key=lambda i: scores[i], reverse=True)

        results: List[SearchResult] = []
        rank = 1
        for idx in ranked_indices:
            if scores[idx] <= 0.0 and len(results) >= top_k:
                break
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
                source_type="bm25"
            ))
            rank += 1
            if len(results) >= top_k:
                break

        return results
