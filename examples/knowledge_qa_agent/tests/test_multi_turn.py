import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.models import Chunk, ActionLink, RerankResult
from src.navigation.router import IntentRouter
from src.agent.qa_engine import KnowledgeAgentEngine


class TestMultiTurnConversation(unittest.TestCase):
    """多轮连续对话、指代消解与会话历史保留验证"""

    def setUp(self):
        self.router = IntentRouter()
        self.parent_chunk = Chunk(
            chunk_id="parent_01",
            doc_id="doc_net",
            title="网关错误排查与流量分析",
            breadcrumbs=["网络服务", "网关与负载均衡", "错误排查"],
            raw_content="ERR_GATEWAY_502 错误通常由于源站证书过期或进程崩溃引起。查看日志路径为 /dashboard/analytics/traffic-errors。",
            contextual_prefix="[网络服务 > 错误排查]",
            is_parent=True,
            action_link=ActionLink(console_path="/dashboard/analytics/traffic-errors", required_permission="Viewer")
        )
        self.child_chunk = Chunk(
            chunk_id="child_01",
            doc_id="doc_net",
            title="502 错误排查",
            breadcrumbs=["网络服务", "错误排查"],
            raw_content="ERR_GATEWAY_502 报错详情",
            contextual_prefix="[网络服务 > 错误排查]",
            parent_id="parent_01",
            is_parent=False
        )
        self.engine = KnowledgeAgentEngine(parent_chunks=[self.parent_chunk])

    def test_query_rewriting_without_history(self):
        """无历史记录时，Query 应保持原样"""
        query = "查看日志"
        rewritten = IntentRouter.rewrite_query_with_history(query, history=[])
        self.assertEqual(rewritten, query)

    def test_pronoun_resolution_and_fast_path_match(self):
        """第一轮提到 502 错误，第二轮用代词'这个错误'，应准确指代并命中快轨"""
        history = [
            {"role": "user", "content": "ERR_GATEWAY_502 错误怎么排查？"},
            {"role": "assistant", "content": "请检查源站进程和 SSL 证书有效性。"}
        ]
        follow_up_query = "查看这个错误日志"

        rewritten = IntentRouter.rewrite_query_with_history(follow_up_query, history)
        self.assertIn("ERR_GATEWAY_502", rewritten)

        # 验证经过指代消解后能正确路由到错误日志页面
        intent = self.router.route(follow_up_query, history=history)
        self.assertTrue(intent.is_fast_path)
        self.assertIsNotNone(intent.matched_action)
        self.assertEqual(intent.matched_action.console_path, "/dashboard/analytics/traffic-errors")

    def test_industrial_equipment_coreference(self):
        """工业场景多轮追问：针对主变压器的后续简短参数追问"""
        history = [
            {"role": "user", "content": "330kV 主变压器油中总烃注意值是多少？"},
            {"role": "assistant", "content": "330kV 主变压器总烃注意值为 150 uL/L。"}
        ]
        follow_up_query = "那乙炔注意值呢？"

        rewritten = IntentRouter.rewrite_query_with_history(follow_up_query, history)
        self.assertIn("主变压器", rewritten)
        self.assertIn("乙炔注意值", rewritten)

    def test_prompt_includes_conversation_history(self):
        """验证多轮会话历史能够正确组装到 XML 提示词中"""
        history = [
            {"role": "user", "content": "什么是 502 报错？"},
            {"role": "assistant", "content": "502 是网关回源失败报错。"}
        ]
        prompt = self.engine.build_prompt(
            query="如何解决？",
            context_str="<document index=\"1\">文档正文</document>",
            conversation_history=history
        )

        self.assertIn("<conversation_history>", prompt)
        self.assertIn("</conversation_history>", prompt)
        self.assertIn("<user>什么是 502 报错？</user>", prompt)
        self.assertIn("<assistant>502 是网关回源失败报错。</assistant>", prompt)
        self.assertIn("<question>", prompt)


if __name__ == "__main__":
    unittest.main()
