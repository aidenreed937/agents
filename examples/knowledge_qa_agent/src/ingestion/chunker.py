"""上下文增强切块器 (Contextual Chunking & Parent-Child Indexing)
借鉴 Anthropic Contextual Retrieval 思想：
为切块补充上下文路径前缀，并将粗粒度阅读块（父块）与细粒度检索块（子块）关联。
"""
from typing import List, Dict, Any, Tuple
from ..models import Chunk, ActionLink, ParsedSection


class ContextualChunker:
    """支持面包屑注入与父子块架构的切块引擎"""

    def __init__(self, child_max_chars: int = 350, overlap_chars: int = 50):
        self.child_max_chars = child_max_chars
        self.overlap_chars = overlap_chars

    def build_parent_and_child_chunks(
        self,
        sections: List[ParsedSection],
        doc_id: str = "doc_cloud_platform_v2026"
    ) -> Tuple[List[Chunk], List[Chunk]]:
        """构建父子块映射体系
        返回:
            parent_chunks: 适合喂给大模型阅读的完整章节块
            child_chunks: 注入了上下文面包屑、适合 BM25 和向量精准命中的细粒度检索块
        """
        parent_chunks: List[Chunk] = []
        child_chunks: List[Chunk] = []

        for sec_idx, sec in enumerate(sections):
            doc_title = sec["doc_title"]
            content = sec["content"]
            action = sec.get("action_link")
            heading = sec.get("heading")
            breadcrumbs = sec.get("heading_path") or ([doc_title, heading] if heading else [doc_title])

            parent_id = f"{doc_id}_parent_{sec_idx}"
            contextual_prefix = f"[上下文路径: {' > '.join(breadcrumbs)}]"
            section_title = " - ".join(breadcrumbs[1:]) if len(breadcrumbs) > 1 else doc_title

            sec_metadata = sec.get("metadata", {})
            sec_tenant = sec_metadata.get("tenant_id", "public")

            # 1. 构建父块 (完整的章节内容)
            parent_chunk = Chunk(
                chunk_id=parent_id,
                doc_id=doc_id,
                title=section_title,
                breadcrumbs=breadcrumbs,
                raw_content=content,
                contextual_prefix=contextual_prefix,
                parent_id=None,
                is_parent=True,
                action_link=action,
                tenant_id=sec_tenant,
                metadata=sec_metadata
            )
            parent_chunks.append(parent_chunk)

            # 2. 构建子块 (保持段落完整性，表格作为独立原子块)
            paragraphs = self._split_paragraphs_preserving_tables(content)
            child_idx = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # 如果段落超长，按标点切分并滑动窗口
                sub_parts = self._split_with_overlap(para, self.child_max_chars, self.overlap_chars)
                for part in sub_parts:
                    child_id = f"{parent_id}_child_{child_idx}"
                    child_chunk = Chunk(
                        chunk_id=child_id,
                        doc_id=doc_id,
                        title=f"{section_title} (片段 {child_idx+1})",
                        breadcrumbs=breadcrumbs,
                        raw_content=part,
                        contextual_prefix=contextual_prefix,
                        parent_id=parent_id,
                        is_parent=False,
                        action_link=action,
                        tenant_id=sec_tenant,
                        metadata=sec_metadata
                    )
                    child_chunks.append(child_chunk)
                    child_idx += 1

        return parent_chunks, child_chunks

    def build_naive_chunks(self, raw_text: str, chunk_size: int = 250) -> List[Chunk]:
        """纯粹按固定字数切分的传统糟糕切片（用于在 demo 中做效果对比）"""
        chunks = []
        clean_text = raw_text.replace("\r", "")
        start = 0
        idx = 0
        while start < len(clean_text):
            end = start + chunk_size
            piece = clean_text[start:end]
            chunks.append(Chunk(
                chunk_id=f"naive_{idx}",
                doc_id="naive_doc",
                title=f"盲切片段 {idx}",
                breadcrumbs=[],
                raw_content=piece,
                contextual_prefix="",
                is_parent=False
            ))
            start = end
            idx += 1
        return chunks

    def _split_paragraphs_preserving_tables(self, text: str) -> List[str]:
        """按空行切分自然段，若遇到表格结构（| 开头）则整表聚合为一个段落"""
        lines = text.splitlines()
        paragraphs = []
        current_para = []
        is_table = False

        for line in lines:
            s_line = line.strip()
            if s_line.startswith("|") and s_line.endswith("|"):
                # 表格行
                is_table = True
                current_para.append(line)
            else:
                if is_table:
                    # 表格结束
                    paragraphs.append("\n".join(current_para))
                    current_para = []
                    is_table = False

                if not s_line:
                    if current_para:
                        paragraphs.append("\n".join(current_para))
                        current_para = []
                else:
                    current_para.append(line)

        if current_para:
            paragraphs.append("\n".join(current_para))

        return paragraphs

    def _split_with_overlap(self, text: str, max_size: int, overlap: int) -> List[str]:
        """对长段落按标点或长度进行带有重叠区的安全切分"""
        if len(text) <= max_size:
            return [text]

        results = []
        start = 0
        while start < len(text):
            end = min(start + max_size, len(text))
            # 尽量在句末标点处断句
            if end < len(text):
                puncts = ["。", "！", "？", "\n", "；"]
                best_cut = -1
                for p in puncts:
                    pos = text.rfind(p, start + max_size // 2, end)
                    if pos > best_cut:
                        best_cut = pos + 1
                if best_cut != -1:
                    end = best_cut

            results.append(text[start:end])
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return results
