import unittest
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.models import Chunk, SearchResult, DiagnosticTask, DiagnosticResult
from src.agent.tools.diagnostic_registry import DiagnosticToolRegistry
from src.retrieval.reranker import CrossEncoderReranker
from src.agent.qa_engine import KnowledgeAgentEngine


class TestFaultInjectionAndDegradation(unittest.TestCase):
    """动态探针异常、超时熔断与零召回防御测试"""

    def setUp(self):
        self.registry = DiagnosticToolRegistry()
        self.parent_chunk = Chunk(
            chunk_id="parent_01",
            doc_id="doc_waf",
            title="WAF 防火墙规则手册",
            breadcrumbs=["安全", "WAF"],
            raw_content="WAF 自定义规则配置说明...",
            contextual_prefix="[安全 > WAF]",
            is_parent=True
        )
        self.engine = KnowledgeAgentEngine(parent_chunks=[self.parent_chunk])

    def test_probe_timeout_circuit_breaker(self):
        """测试探针执行超时熔断机制：慢探针应在设定超时内中断并返回 TIMEOUT 状态"""
        def slow_probe():
            time.sleep(1.0)
            return DiagnosticResult(
                tool_name="slow_probe",
                status="HEALTHY",
                summary="慢探针执行成功"
            )

        self.registry.register_tool("slow_probe", "模拟延迟卡死探针", slow_probe)

        tasks = [DiagnosticTask(tool_name="slow_probe", params={})]
        t0 = time.perf_counter()
        results = self.registry.execute_tasks_parallel(tasks, timeout_seconds=0.1)
        elapsed = time.perf_counter() - t0

        # 耗时应当接近 0.1s，而不是等待 1.0s
        self.assertLess(elapsed, 0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "TIMEOUT")
        self.assertIn("超时", results[0].summary)

    def test_probe_exception_resilience(self):
        """测试探针崩溃容错机制：探针抛出异常时不应崩溃，返回 CRITICAL 状态"""
        def crashing_probe():
            raise ConnectionResetError("底层遥测通道连接被重置 (ECONNRESET)")

        self.registry.register_tool("crashing_probe", "抛出异常的探针", crashing_probe)

        tasks = [DiagnosticTask(tool_name="crashing_probe", params={})]
        results = self.registry.execute_tasks_parallel(tasks)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "CRITICAL")
        self.assertIn("抛出异常", results[0].summary)

    def test_partial_probe_failure_formatting(self):
        """测试探针部分失败时，XML 提示词格式化应准确记录健康、异常与未知状态"""
        results = [
            DiagnosticResult(tool_name="probe_a", status="HEALTHY", summary="正常运行", metrics={"qps": 100}),
            DiagnosticResult(tool_name="probe_b", status="CRITICAL", summary="源站宕机", metrics={"code": 502}),
            DiagnosticResult(tool_name="probe_c", status="TIMEOUT", summary="网络超时", metrics={})
        ]

        xml_output = DiagnosticToolRegistry.format_diagnostics_for_prompt(results)
        self.assertIn('<probe index="1" tool="probe_a" status="HEALTHY">', xml_output)
        self.assertIn('<probe index="2" tool="probe_b" status="CRITICAL">', xml_output)
        self.assertIn('<probe index="3" tool="probe_c" status="TIMEOUT">', xml_output)

    def test_zero_recall_and_low_confidence_refusal(self):
        """测试完全不命中与精排低分过滤：候选切片均低于阈值时，引擎应安全拒答不产生幻觉"""
        reranker = CrossEncoderReranker(min_relevance_threshold=0.50)

        unrelated_chunk = Chunk(
            chunk_id="chunk_unrelated",
            doc_id="doc_other",
            title="办公网络打印机驱动安装指南",
            breadcrumbs=["内部IT", "外设支持"],
            raw_content="请在控制面板添加网络打印机 IP 192.168.1.200",
            contextual_prefix="[内部IT > 打印机]",
            is_parent=False
        )
        candidates = [
            SearchResult(chunk=unrelated_chunk, score=0.01, rank=1, source_type="bm25")
        ]

        # 用户询问高难度电网绝缘问题，但召回库仅有打印机
        query = "请给出 500kV 主变压器乙炔注意值超标时的脱气试验方案"
        rerank_results = reranker.rerank(query, candidates)

        # 重排器因相关度过低应全量剔除
        self.assertEqual(len(rerank_results), 0)

        # 问答引擎应触发安全拒答保底
        answer_pkg = self.engine.generate_grounded_answer(query, rerank_results)
        self.assertIn("未检索到与您的问题相关的有效信息", answer_pkg["answer"])
        self.assertEqual(len(answer_pkg["citations"]), 0)


if __name__ == "__main__":
    unittest.main()
