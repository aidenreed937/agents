"""FastAPI 业务服务入口（Enterprise Expense Agent Web Gateway）
提供与前后端解耦交互的 RESTful & Server-Sent Events (SSE) 接口。
"""
import uuid
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .schemas import SubmitExpenseRequest, ResumeExpenseRequest, PresetScenario, TaskSummary
from .service import ExpenseApiService

app = FastAPI(
    title="Enterprise Expense Agent API",
    description="基于 LangGraph 状态图与人在回路（HITL）的企业级差旅报销智能体服务网关",
    version="1.0.0"
)

# 开启跨域支持（前后端分离标配）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = ExpenseApiService()


@app.get("/api/health", tags=["System"])
def health_check():
    """服务健康检查"""
    return {
        "status": "healthy",
        "service": "enterprise-expense-agent",
        "engine": "LangGraph StateGraph",
        "durable_checkpointer": "LangGraphFileCheckpointer"
    }


@app.get("/api/expense/presets", response_model=List[PresetScenario], tags=["Expense"])
def get_presets():
    """获取预置的5大典型报销业务测试场景"""
    return service.get_presets()


@app.get("/api/expense/graph", tags=["Expense"])
def get_graph():
    """获取 LangGraph 状态图的 Mermaid 拓扑图源码"""
    return {
        "mermaid": service.get_mermaid_graph(),
        "nodes": [
            "security_guardrail",
            "parse_intent",
            "fetch_data_assets",
            "cross_validate_claim",
            "governance_check",
            "prepare_hitl",
            "wait_for_hitl",
            "create_draft"
        ]
    }


@app.post("/api/expense/submit", tags=["Expense"])
async def submit_expense_sync(req: SubmitExpenseRequest):
    """同步提交报销申请并等待最终执行结果"""
    thread_id = req.thread_id or f"th_{uuid.uuid4().hex[:10]}"
    try:
        final_state = await service.submit_sync(
            thread_id=thread_id,
            employee_id=req.employee_id,
            query=req.query
        )
        return {
            "thread_id": thread_id,
            "status": final_state.get("status"),
            "state": final_state
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工作流执行异常: {str(e)}"
        )


@app.get("/api/expense/submit-stream", tags=["Expense"])
async def submit_expense_stream(
    query: str = Query(..., description="自然语言提报描述"),
    employee_id: str = Query("EMP-1001", description="员工工号"),
    thread_id: Optional[str] = Query(None, description="会话ID")
):
    """Server-Sent Events (SSE) 流式提交接口，实时推送 LangGraph 各节点流转事件"""
    tid = thread_id or f"th_{uuid.uuid4().hex[:10]}"
    
    return StreamingResponse(
        service.stream_submit(thread_id=tid, employee_id=employee_id, query=query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/expense/tasks", tags=["Tasks"])
def list_tasks(status: Optional[str] = Query(None, description="状态过滤，如 PAUSED_HITL, COMPLETED")):
    """查询报销任务/工单列表"""
    return service.list_tasks(status_filter=status)


@app.get("/api/expense/task/{thread_id}", tags=["Tasks"])
def get_task(thread_id: str):
    """获取指定任务/工单的详细全生命周期快照"""
    task = service.get_task(thread_id)
    if not task:
        raise HTTPException(status_code=404, detail="未找到对应的报销任务快照")
    return task


@app.post("/api/expense/resume", tags=["HITL"])
def resume_hitl_task(req: ResumeExpenseRequest):
    """人在回路（HITL）审批唤醒接口
    用于主管/财务审批超标单据，将处于 wait_for_hitl 挂起的 LangGraph 状态图原位恢复并推进建单。
    """
    try:
        updated_state = service.resume_task(
            thread_id=req.thread_id,
            operator_role=req.operator_role,
            operator_id=req.operator_id,
            approved=req.approved,
            comment=req.comment
        )
        return {
            "status": "success",
            "thread_id": req.thread_id,
            "new_status": updated_state.get("status"),
            "draft": updated_state.get("reimbursement_draft"),
            "state": updated_state
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"人在回路恢复失败: {str(e)}"
        )
