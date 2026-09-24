"""智能体工具集注册层（Tool Registry）
所有暴露给 Agent 的工具均在此声明，并封装前置 RBAC 鉴权与入参类型校验。
同时提供生产级异步并发调用接口（Async I/O）。
"""
import asyncio
from typing import Dict, Any, Optional
from ..data_assets.invoice_center import InvoiceCenter
from ..data_assets.oa_trip_center import OATripCenter
from ..data_assets.policy_store import PolicyStore
from ..governance.rbac import Role, Action, RBACManager, SecurityContext

# 模拟外部财务系统草单底表存储（模拟两阶段事务与反查能力）
_FINANCE_DRAFT_DB: Dict[str, Dict[str, Any]] = {}

class ExpenseTools:
    """注册给 Agent 的受控工具集"""

    @staticmethod
    def _get_context(ctx: Optional[SecurityContext]) -> SecurityContext:
        return ctx if ctx is not None else SecurityContext.agent_system_context()

    @staticmethod
    def query_invoice(invoice_code: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：通过发票代码查询中台发票信息与真伪（同步版）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_INVOICE)
        return InvoiceCenter.verify_and_get_invoice(invoice_code)

    @staticmethod
    async def async_query_invoice(invoice_code: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：异步非阻塞查询发票中台（模拟网络 I/O 耗时 50ms）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_INVOICE)
        await asyncio.sleep(0.05)
        return InvoiceCenter.verify_and_get_invoice(invoice_code)

    @staticmethod
    def query_trip(employee_id: str, date: str, city: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：通过 OA 系统查询员工已审批的差旅记录（同步版）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_TRIP)
        return OATripCenter.query_approved_trip(employee_id, date, city)

    @staticmethod
    async def async_query_trip(employee_id: str, date: str, city: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：异步非阻塞查询 OA 差旅审批中台（模拟网络 I/O 耗时 50ms）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_TRIP)
        await asyncio.sleep(0.05)
        return OATripCenter.query_approved_trip(employee_id, date, city)

    @staticmethod
    def query_policy(city: str, category: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：查询特定城市和类别的报销政策上限（同步版）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_POLICY)
        return PolicyStore.get_expense_limit(city, category)

    @staticmethod
    async def async_query_policy(city: str, category: str, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """工具：异步非阻塞检索企业制度知识库（模拟网络 I/O 耗时 50ms）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.READ_POLICY)
        await asyncio.sleep(0.05)
        return PolicyStore.get_expense_limit(city, category)

    @staticmethod
    def query_draft_by_idempotency_key(idempotency_key: str, ctx: Optional[SecurityContext] = None) -> Optional[Dict[str, Any]]:
        """工具：通过幂等键向外部财务系统反查已有草单（用于崩溃恢复与超时探测）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.CREATE_DRAFT)
        return _FINANCE_DRAFT_DB.get(idempotency_key)

    @staticmethod
    def create_reimbursement_draft(
        draft_data: Dict[str, Any], 
        idempotency_key: Optional[str] = None, 
        ctx: Optional[SecurityContext] = None
    ) -> Dict[str, Any]:
        """工具：在财务系统创建预审报销草单（允许 Agent 调用）"""
        context = ExpenseTools._get_context(ctx)
        RBACManager.verify(context, Action.CREATE_DRAFT)

        # 若下游财务系统已存在该幂等键的草单，直接返回历史记录（系统级防重）
        if idempotency_key and idempotency_key in _FINANCE_DRAFT_DB:
            return _FINANCE_DRAFT_DB[idempotency_key]

        emp_suffix = str(draft_data.get('employee_id', 'unknown'))[-4:]
        draft_id = f"DRAFT-2026-EXP-{emp_suffix}"
        result = {
            "success": True,
            "draft_id": draft_id,
            "status": "DRAFT_SUBMITTED",
            "idempotency_key": idempotency_key,
            "created_by": context.user_id,
            "data": draft_data
        }
        if idempotency_key:
            _FINANCE_DRAFT_DB[idempotency_key] = result
        return result

    @staticmethod
    def execute_direct_payment(account: str, amount: float, ctx: Optional[SecurityContext] = None) -> Dict[str, Any]:
        """
        高危工具：直接执行银企互联打款转账！
        当无治理 Agent 尝试调用该接口时，RBAC 将直接拦截并抛出异常。
        """
        context = ExpenseTools._get_context(ctx)
        # 强制进行权限校验（Agent 角色在此必被拦截）
        RBACManager.verify(context, Action.EXECUTE_PAYMENT)
        
        return {
            "success": True,
            "message": f"已成功向账户 {account} 划扣打款 {amount} 元"
        }

