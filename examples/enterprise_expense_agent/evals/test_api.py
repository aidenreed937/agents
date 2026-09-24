"""API 自动化集成测试（FastAPI & LangGraph 端到端接口验证）
验证：
1. /api/health 健康探测
2. /api/expense/presets 预置场景提取
3. /api/expense/graph 拓扑图导出
4. /api/expense/submit 标准合规直通建单
5. /api/expense/submit 差旅超标触发表单人在回路（PAUSED_HITL）
6. /api/expense/tasks 挂起任务发现与列表检索
7. /api/expense/resume 人在回路唤醒并完成草单闭环
8. /api/expense/submit-stream SSE 流式事件推送
"""
import sys
import os
import unittest
import shutil

# 注入 src 目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from starlette.testclient import TestClient
from enterprise_expense_agent.api.app import app, service


class TestExpenseAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_checkpoints_dir = os.path.abspath(
            os.path.join(CURRENT_DIR, "..", ".test_api_checkpoints")
        )
        os.makedirs(cls.test_checkpoints_dir, exist_ok=True)
        # 隔离测试检查点目录
        service.checkpoints_dir = cls.test_checkpoints_dir
        service.checkpointer.storage_dir = cls.test_checkpoints_dir

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_checkpoints_dir):
            shutil.rmtree(cls.test_checkpoints_dir, ignore_errors=True)

    def test_01_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["engine"], "LangGraph StateGraph")

    def test_02_presets(self):
        res = self.client.get("/api/expense/presets")
        self.assertEqual(res.status_code, 200)
        presets = res.json()
        self.assertGreaterEqual(len(presets), 5)
        categories = [p["category"] for p in presets]
        self.assertIn("NORMAL", categories)
        self.assertIn("RISK_OVER_BUDGET", categories)

    def test_03_graph_mermaid(self):
        res = self.client.get("/api/expense/graph")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("mermaid", data)
        self.assertIn("security_guardrail", data["nodes"])
        self.assertIn("wait_for_hitl", data["nodes"])

    def test_04_submit_normal_sync(self):
        thread_id = "test_api_th_normal_001"
        payload = {
            "thread_id": thread_id,
            "employee_id": "EMP-1001",
            "query": "帮我报销2026年3月20日在北京出差的打车费220元，发票代码为 INV-2026-901"
        }
        res = self.client.post("/api/expense/submit", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIsNotNone(data["state"].get("reimbursement_draft"))

    def test_05_submit_over_budget_hitl_and_resume(self):
        thread_id = "test_api_th_overlimit_001"
        payload = {
            "thread_id": thread_id,
            "employee_id": "EMP-1007",
            "query": "报销北京打车费 520 元，发票代码 INV-2026-905"
        }
        # 1. 提交超额报销，预期在 wait_for_hitl 挂起
        res = self.client.post("/api/expense/submit", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "PAUSED_HITL")

        # 2. 从 tasks 列表检索该工单
        tasks_res = self.client.get("/api/expense/tasks?status=PAUSED_HITL")
        self.assertEqual(tasks_res.status_code, 200)
        tasks = tasks_res.json()
        found = any(t["thread_id"] == thread_id for t in tasks)
        self.assertTrue(found, "未在 PAUSED_HITL 列表中找到挂起任务")

        # 3. 模拟业务总监执行人在回路审批唤醒
        resume_payload = {
            "thread_id": thread_id,
            "operator_role": "DIRECTOR",
            "operator_id": "DIR-8888",
            "approved": True,
            "comment": "特批通过该笔差旅超额支出"
        }
        resume_res = self.client.post("/api/expense/resume", json=resume_payload)
        self.assertEqual(resume_res.status_code, 200)
        res_data = resume_res.json()
        self.assertEqual(res_data["status"], "success")
        self.assertEqual(res_data["new_status"], "COMPLETED")
        self.assertIsNotNone(res_data["draft"])
        self.assertEqual(res_data["draft"]["data"]["total_amount"], 520.0)

    def test_06_submit_stream_sse(self):
        params = {
            "thread_id": "test_api_stream_001",
            "employee_id": "EMP-1001",
            "query": "帮我报销2026年3月20日在北京出差的打车费220元，发票代码为 INV-2026-901"
        }
        res = self.client.get("/api/expense/submit-stream", params=params)
        self.assertEqual(res.status_code, 200)
        text = res.text
        self.assertIn("event: workflow_started", text)
        self.assertIn("event: node_executed", text)
        self.assertIn("event: workflow_finished", text)


if __name__ == "__main__":
    unittest.main()
