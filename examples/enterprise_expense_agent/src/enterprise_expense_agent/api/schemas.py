"""API 数据模型（Pydantic Schemas）
定义前后端分离交互的请求与响应契约。
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SubmitExpenseRequest(BaseModel):
    thread_id: Optional[str] = Field(None, description="会话/线程唯一ID，若为空则自动生成")
    employee_id: str = Field("EMP-1001", description="提报员工工号")
    query: str = Field(..., description="自然语言提报描述")


class ResumeExpenseRequest(BaseModel):
    thread_id: str = Field(..., description="待恢复执行的线程ID")
    operator_role: str = Field("DIRECTOR", description="审批人角色: DIRECTOR / FINANCE_CLERK")
    operator_id: str = Field("DIR-9001", description="审批人工号")
    approved: bool = Field(True, description="是否批准")
    comment: str = Field("核验业务真实且确系紧急需要，特批通过", description="审批批注说明")


class TaskSummary(BaseModel):
    thread_id: str
    employee_id: str
    query: str
    status: str
    created_at: str
    updated_at: str
    category: Optional[str] = None
    city: Optional[str] = None
    amount: Optional[float] = None
    invoice_code: Optional[str] = None
    hitl_reason: Optional[str] = None
    reimbursement_draft_id: Optional[str] = None


class PresetScenario(BaseModel):
    id: str
    title: str
    category: str
    badge: str
    description: str
    employee_id: str
    query: str
