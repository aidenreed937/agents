import unittest
import os
import sys
import shutil
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.models import Chunk, RerankResult
from src.agent.qa_engine import KnowledgeAgentEngine
from src.storage.sqlite_store import SQLiteLocalStore


class TestContextBudgetAndLifecycle(unittest.TestCase):
    """Token 预算管理、长上下文动态截断与文档生命周期删除测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_lifecycle.db")
        self.store = SQLiteLocalStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_context_budget_dynamic_truncation(self):
        """测试父块膨胀时的上下文预算动态截断与标签闭合完整性"""
        # 构造两个超大父块 (每个 3000 字)
        huge_parent_1 = Chunk(
            chunk_id="parent_huge_01",
            doc_id="doc_huge",
            title="大型变电站主变压器运维总则 第一章",
            breadcrumbs=["规程", "第一章"],
            raw_content="【规程条文 A】" + ("详细参数规范指标说明。" * 150),  # ~2000+ 字
            contextual_prefix="[规程 > 第一章]",
            is_parent=True
        )
        huge_parent_2 = Chunk(
            chunk_id="parent_huge_02",
            doc_id="doc_huge",
            title="大型变电站主变压器运维总则 第二章",
            breadcrumbs=["规程", "第二章"],
            raw_content="【规程条文 B】" + ("详细应急处置流程步骤。" * 150),  # ~2000+ 字
            contextual_prefix="[规程 > 第二章]",
            is_parent=True
        )

        engine = KnowledgeAgentEngine(parent_chunks=[huge_parent_1, huge_parent_2])

        rerank_results = [
            RerankResult(chunk=huge_parent_1, relevance_score=0.95, rationale="top1"),
            RerankResult(chunk=huge_parent_2, relevance_score=0.85, rationale="top2"),
        ]

        # 设定严格的字符预算限制为 1500 字符
        max_budget = 1500
        context_str, _, restored_chunks = engine.assemble_context_with_parent_restoration(
            rerank_results, max_context_chars=max_budget
        )

        # 1. 验证上下文总长度受控（允许包含基础标签格式开销，不超过预算设定上限 + 500）
        self.assertLessEqual(len(context_str), max_budget + 500)

        # 2. 验证出现截断标识
        self.assertIn("超出最大上下文 Token 预算已自动截断", context_str)

        # 3. 验证 XML document 标签仍然成对闭合
        open_doc_count = context_str.count("<document")
        close_doc_count = context_str.count("</document>")
        self.assertEqual(open_doc_count, close_doc_count, "截断后 XML document 标签不匹配")

    def test_document_lifecycle_and_deletion(self):
        """测试文档下架与删除生命周期：删除后 FTS5 与元数据彻底清理，不留脏索引"""
        # 写入文档 A (2 个切片) 与 文档 B (1 个切片)
        chunks_doc_a = [
            Chunk(
                chunk_id="doc_a_chunk_1",
                doc_id="doc_expired_v1",
                title="已废止老版本变压器规程 1996版",
                breadcrumbs=["老规程", "总则"],
                raw_content="旧版注意值：总烃 300 uL/L，已废止。",
                contextual_prefix="[老规程]",
                is_parent=False
            ),
            Chunk(
                chunk_id="doc_a_chunk_2",
                doc_id="doc_expired_v1",
                title="已废止老版本变压器规程 附录",
                breadcrumbs=["老规程", "附录"],
                raw_content="旧版编码规则说明，现已废止停用。",
                contextual_prefix="[老规程]",
                is_parent=False
            )
        ]
        chunk_doc_b = Chunk(
            chunk_id="doc_b_chunk_1",
            doc_id="doc_current_v2",
            title="现行有效规程 2026最新版",
            breadcrumbs=["新规程", "总则"],
            raw_content="现行标准注意值：总烃 150 uL/L，严格执行。",
            contextual_prefix="[新规程]",
            is_parent=False
        )

        self.store.save_chunks(chunks_doc_a + [chunk_doc_b])

        # 1. 删除前：旧规程可以检索到
        res_before = self.store.fts5_search("已废止老版本", top_k=5)
        self.assertEqual(len(res_before), 2)

        # 2. 执行文档下架物理删除
        deleted_count = self.store.delete_document("doc_expired_v1")
        self.assertEqual(deleted_count, 2)

        # 3. 删除后：再次搜索旧规程关键字，应完全不可检索 (0 命中)
        res_after_a = self.store.fts5_search("已废止老版本", top_k=5)
        self.assertEqual(len(res_after_a), 0)

        # 4. 新规程不受任何影响，依然能精准命中
        res_after_b = self.store.fts5_search("现行有效规程", top_k=5)
        self.assertEqual(len(res_after_b), 1)
        self.assertEqual(res_after_b[0].chunk.doc_id, "doc_current_v2")


if __name__ == "__main__":
    unittest.main()
