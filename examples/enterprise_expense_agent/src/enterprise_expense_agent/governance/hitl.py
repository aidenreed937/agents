"""业务治理层：人在回路（Human-in-the-Loop, HITL）
实现状态机挂起（Interrupt）、人工审批单分发、授权回调与流程恢复（Resume）。
将审批单与特定的 ValidatedExpenseClaim version_hash 强绑定，防止旁路数据篡改。
"""
import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
from .rbac import Role, Action, RBACManager, SecurityContext

@dataclass
class ApprovalTicket:
    ticket_id: str
    target_role: Role
    employee_id: str
    amount: float
    overlimit_amount: float
    reason: str
    claim_id: str
    claim_version_hash: str     # 强绑定已核验申请单版本哈希
    status: str  # "PENDING", "APPROVED", "REJECTED"
    approver_id: Optional[str] = None
    comment: Optional[str] = None

class HITLManager:
    """人在回路审批管理器（状态挂起与恢复中心）"""

    def __init__(self):
        self._tickets: Dict[str, ApprovalTicket] = {}

    def create_interrupt_ticket(
        self, 
        employee_id: str, 
        amount: float, 
        overlimit_amount: float, 
        reason: str,
        claim_id: str = "CLAIM-DEFAULT",
        claim_version_hash: str = "HASH-DEFAULT"
    ) -> ApprovalTicket:
        """
        在状态机节点中挂起执行，创建人工审批单，强绑定申请版本指纹
        """
        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        ticket = ApprovalTicket(
            ticket_id=ticket_id,
            target_role=Role.DIRECTOR,
            employee_id=employee_id,
            amount=amount,
            overlimit_amount=overlimit_amount,
            reason=reason,
            claim_id=claim_id,
            claim_version_hash=claim_version_hash,
            status="PENDING"
        )
        self._tickets[ticket_id] = ticket
        return ticket

    def register_ticket(self, ticket: ApprovalTicket):
        """恢复持久化检查点时同步注册工单"""
        self._tickets[ticket.ticket_id] = ticket

    def submit_decision(
        self, 
        ticket_id: str, 
        operator: Union[Role, SecurityContext], 
        is_approved: bool, 
        comment: str,
        expected_version_hash: Optional[str] = None
    ) -> ApprovalTicket:
        """
        人工在 Web / 审批流点击确认，注入决策以恢复执行
        """
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"审批单 {ticket_id} 不存在")

        # 权限校验：具备 APPROVE_OVERLIMIT 权限
        RBACManager.verify(operator, Action.APPROVE_OVERLIMIT)

        # 契约防篡改校验：审批单版本必须与申请版本严格一致
        if expected_version_hash and ticket.claim_version_hash != expected_version_hash:
            raise ValueError(
                f"[审批契约校验失败] 申请数据在审批期间已被更改！"
                f"工单版本 ({ticket.claim_version_hash[:8]}...) 与当前版本 ({expected_version_hash[:8]}...) 不一致！"
            )

        approver_id = operator.user_id if isinstance(operator, SecurityContext) else "SYSTEM_ADMIN"
        ticket.status = "APPROVED" if is_approved else "REJECTED"
        ticket.approver_id = approver_id
        ticket.comment = comment
        return ticket

