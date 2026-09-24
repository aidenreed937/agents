"""真实多进程与网络端口端到端测试 (Live Multi-Process E2E Network Verification)
在独立网络端口上真实拉起：
1. FastAPI 后端服务 (端口 8765)
2. Web 前端静态服务器 (端口 8766)
并通过真实 HTTP 套接字通信完成全链路闭环验证。
"""
import sys
import os
import time
import subprocess
import signal
import urllib.request
import json
import uuid

BACKEND_PORT = 8765
FRONTEND_PORT = 8766

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
FRONTEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "frontend"))
PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable


def wait_for_url(url: str, timeout_sec: float = 6.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as res:
                if res.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def http_post_json(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5.0) as res:
        return json.loads(res.read().decode("utf-8"))


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5.0) as res:
        return json.loads(res.read().decode("utf-8"))


def main():
    print("==================================================================")
    print(">>> 启动真实网络端口端到端测试 (Live Port E2E Verification) <<<")
    print(f"Backend  Target: http://127.0.0.1:{BACKEND_PORT}")
    print(f"Frontend Target: http://127.0.0.1:{FRONTEND_PORT}")
    print("==================================================================")

    # 1. 启动后端 FastAPI 进程
    backend_cmd = [
        PYTHON_BIN,
        os.path.join(PROJECT_ROOT, "examples", "enterprise_expense_agent", "server.py"),
        "--port", str(BACKEND_PORT)
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT
    )

    # 2. 启动前端 Web 服务器 (优先托管 Vite 编译产物 dist)
    serve_dir = os.path.join(FRONTEND_DIR, "dist") if os.path.exists(os.path.join(FRONTEND_DIR, "dist")) else FRONTEND_DIR
    frontend_cmd = [
        PYTHON_BIN,
        "-m", "http.server", str(FRONTEND_PORT),
        "--directory", serve_dir
    ]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=PROJECT_ROOT
    )

    try:
        # 3. 探活检测
        print("\n[Step 1/6] 探活探测：等待前后端进程端口响应...")
        backend_ready = wait_for_url(f"http://127.0.0.1:{BACKEND_PORT}/api/health", timeout_sec=8.0)
        assert backend_ready, "FastAPI 后端端口探活超时失败！"
        frontend_ready = wait_for_url(f"http://127.0.0.1:{FRONTEND_PORT}/index.html", timeout_sec=6.0)
        assert frontend_ready, "前端 Web 静态服务端口探活超时失败！"
        print("  ✓ 后端 FastAPI 8765 端口在线响应 (HTTP 200)")
        print("  ✓ 前端 Web 8766 端口在线响应 (HTTP 200)")

        # 4. 前端静态 HTML 校验
        print("\n[Step 2/6] 前端 React 控制台静态资源抓取校验...")
        with urllib.request.urlopen(f"http://127.0.0.1:{FRONTEND_PORT}/index.html") as res:
            html = res.read().decode("utf-8")
            assert "Enterprise Expense Agent" in html
            assert "id=\"root\"" in html
        print("  ✓ 前端 React 应用主页挂载点完整加载 (root container verified)")

        # 5. 场景 1: 标准合规报销
        print("\n[Step 3/6] 发送标准合规报销请求 (HTTP POST /api/expense/submit)...")
        th_normal = f"live_th_normal_{uuid.uuid4().hex[:6]}"
        normal_payload = {
            "thread_id": th_normal,
            "employee_id": "EMP-1001",
            "query": "帮我报销2026年3月20日在北京出差的打车费220元，发票代码为 INV-2026-901"
        }
        res_normal = http_post_json(f"http://127.0.0.1:{BACKEND_PORT}/api/expense/submit", normal_payload)
        assert res_normal["status"] == "COMPLETED", f"期望 COMPLETED，实际: {res_normal['status']}"
        draft_id = res_normal["state"]["reimbursement_draft"]["draft_id"]
        assert draft_id.startswith("DRAFT-"), "未生成有效报销草单"
        print(f"  ✓ 成功闭环生成财务草单: {draft_id}")

        # 6. 场景 2: 费用超标人在回路 (HITL) 挂起
        print("\n[Step 4/6] 发送差旅超标报销请求 (触发 LangGraph interrupt 挂起)...")
        th_hitl = f"live_th_hitl_{uuid.uuid4().hex[:6]}"
        hitl_payload = {
            "thread_id": th_hitl,
            "employee_id": "EMP-1007",
            "query": "报销北京打车费 520 元，发票代码 INV-2026-905"
        }
        res_hitl = http_post_json(f"http://127.0.0.1:{BACKEND_PORT}/api/expense/submit", hitl_payload)
        assert res_hitl["status"] == "PAUSED_HITL", f"期望 PAUSED_HITL，实际: {res_hitl['status']}"
        print(f"  ✓ LangGraph 状态图已在断点冻结挂起: [Thread: {th_hitl}]")

        # 7. 场景 3: 审批中心查询待办
        print("\n[Step 5/6] 审批端拉取待办列表 (HTTP GET /api/expense/tasks?status=PAUSED_HITL)...")
        tasks_list = http_get_json(f"http://127.0.0.1:{BACKEND_PORT}/api/expense/tasks?status=PAUSED_HITL")
        matched = [t for t in tasks_list if t["thread_id"] == th_hitl]
        assert len(matched) > 0, "未能从待办列表中发现挂起任务"
        print(f"  ✓ 待办中心成功检索到挂起工单: 超标额 {matched[0].get('amount')}元")

        # 8. 场景 4: 业务总监特批唤醒
        print("\n[Step 6/6] 业务总监执行人在回路特批 (HTTP POST /api/expense/resume)...")
        resume_payload = {
            "thread_id": th_hitl,
            "operator_role": "DIRECTOR",
            "operator_id": "DIR-LIVE-9001",
            "approved": True,
            "comment": "真实网络环境测试：特批北京紧急打车超标支出"
        }
        res_resumed = http_post_json(f"http://127.0.0.1:{BACKEND_PORT}/api/expense/resume", resume_payload)
        assert res_resumed["status"] == "success"
        assert res_resumed["new_status"] == "COMPLETED"
        hitl_draft_id = res_resumed["draft"]["draft_id"]
        total_amt = res_resumed["draft"]["data"]["total_amount"]
        assert hitl_draft_id.startswith("DRAFT-")
        assert total_amt == 520.0
        print(f"  ✓ 成功通过 Command(resume=...) 唤醒并生成草单: {hitl_draft_id} (金额: ¥{total_amt})")

        print("\n==================================================================")
        print(">>> 真实多进程网络端口端到端测试全部通过 (ALL CHECKS PASSED)! <<<")
        print("==================================================================")

    finally:
        # 清理子进程
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=2.0)
            frontend_proc.wait(timeout=2.0)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()


if __name__ == "__main__":
    main()
