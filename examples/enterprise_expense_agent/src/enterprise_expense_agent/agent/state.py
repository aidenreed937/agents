"""智能体状态机状态（State）定义
类似于 LangGraph TypedDict / Pydantic BaseModel，维护全链路的执行上下文与状态持久化快照。
支持与 Checkpointer 互相序列化与反序列化，支持基于 thread_id 的持久化恢复。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from ..governance.risk_checker import RiskAssessment
from ..governance.hitl import ApprovalTicket, Role
from ..governance.rbac import SecurityContext
from .schema import ValidatedExpenseClaim, ClaimStatus

@dataclass
class ExpenseAgentState:
    """差旅报销智能体全局流转状态"""
    employee_id: str
    raw_user_input: str
    thread_id: str = "default_thread_001"  # 会话/线程唯一 ID（用于断点持久化与恢复）
    security_context: Optional[SecurityContext] = None
    
    # 权威业务数据契约（经发票、行程、政策核验后的单据快照）
    validated_claim: Optional[ValidatedExpenseClaim] = None

    # 模型分级路由与算力指标
    model_used: Optional[str] = None
    token_cost_ratio: float = 1.0
    io_duration_ms: float = 0.0
    
    # 意图理解与结构化提取结果（大模型层候选产出）
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    
    # 显式信息缺失与反问追问控制（平衡灵活与规则）
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)
    
    # 数据资产核验结果（数据资产层产出）
    invoice_data: Optional[Dict[str, Any]] = None
    trip_data: Optional[Dict[str, Any]] = None
    policy_data: Optional[Dict[str, Any]] = None
    
    # 业务治理与风控评估（治理层产出）
    risk_assessment: Optional[RiskAssessment] = None
    
    # 人在回路中断审批单（HITL 产出）
    hitl_ticket: Optional[ApprovalTicket] = None
    
    # 最终业务闭环生成的报销草单
    reimbursement_draft: Optional[Dict[str, Any]] = None
    
    # Layer 1: 安全与隐私防护
    redacted_input: Optional[str] = None
    pii_vault: Dict[str, str] = field(default_factory=dict)
    guardrail_blocked: bool = False
    guardrail_attack_type: Optional[str] = None
    guardrail_reason: Optional[str] = None
    
    # Layer 2: 语义缓存（仅用于只读问答或可选调试，主交易链路已剥离）
    is_cache_hit: bool = False
    cache_similarity: float = 0.0
    
    # Layer 3: 提示词版本
    prompt_version: str = "v1.1"
    
    # Layer 5: 接口幂等控制
    idempotency_key: Optional[str] = None
    is_idempotent_duplicate: bool = False

    # 状态机流转控制
    # INITIALIZED, REJECTED_GUARDRAIL, WAITING_CLARIFICATION, DATA_VALIDATED, PAUSED_HITL, APPROVED, COMPLETED, FAILED
    status: str = "INITIALIZED"  
    error: Optional[str] = None
    
    # 全链路 Trace 日志（可观测性）
    trace_logs: List[str] = field(default_factory=list)

    def log_step(self, step_name: str, message: str):
        """记录链路追踪日志"""
        log_entry = f"[{step_name}] {message}"
        self.trace_logs.append(log_entry)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 字典用于存盘"""
        data = asdict(self)
        # 特殊枚举或复杂对象处理
        if self.hitl_ticket:
            data["hitl_ticket"] = asdict(self.hitl_ticket)
            data["hitl_ticket"]["target_role"] = self.hitl_ticket.target_role.value
        if self.risk_assessment:
            data["risk_assessment"] = asdict(self.risk_assessment)
        if self.security_context:
            data["security_context"] = asdict(self.security_context)
            data["security_context"]["role"] = self.security_context.role.value
        if self.validated_claim:
            data["validated_claim"] = asdict(self.validated_claim)
            data["validated_claim"]["status"] = self.validated_claim.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpenseAgentState":
        """从字典或 LangGraph 状态反序列化恢复状态"""
        clean_data = {k: v for k, v in data.items() if not k.startswith("__")}
        hitl_raw = clean_data.pop("hitl_ticket", None)
        risk_raw = clean_data.pop("risk_assessment", None)
        sec_raw = clean_data.pop("security_context", None)
        claim_raw = clean_data.pop("validated_claim", None)

        hitl_ticket = None
        if hitl_raw:
            if isinstance(hitl_raw, dict):
                hitl_dict = dict(hitl_raw)
                hitl_dict["target_role"] = Role(hitl_dict["target_role"])
                hitl_ticket = ApprovalTicket(**hitl_dict)
            else:
                hitl_ticket = hitl_raw

        risk_assessment = None
        if risk_raw:
            if isinstance(risk_raw, dict):
                risk_assessment = RiskAssessment(**risk_raw)
            else:
                risk_assessment = risk_raw

        security_context = None
        if sec_raw:
            if isinstance(sec_raw, dict):
                sec_dict = dict(sec_raw)
                sec_dict["role"] = Role(sec_dict["role"])
                security_context = SecurityContext(**sec_dict)
            else:
                security_context = sec_raw

        validated_claim = None
        if claim_raw:
            if isinstance(claim_raw, dict):
                claim_dict = dict(claim_raw)
                claim_dict["status"] = ClaimStatus(claim_dict["status"])
                validated_claim = ValidatedExpenseClaim(**claim_dict)
            else:
                validated_claim = claim_raw

        return cls(
            hitl_ticket=hitl_ticket,
            risk_assessment=risk_assessment,
            security_context=security_context,
            validated_claim=validated_claim,
            **clean_data
        )

    @classmethod
    def from_langgraph(cls, res: Dict[str, Any]) -> "ExpenseAgentState":
        """从 LangGraph 返回字典转换为 ExpenseAgentState 实体"""
        return cls.from_dict(res)

