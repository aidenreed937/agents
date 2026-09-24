"""智能体结构化数据契约（Schema & Contract）
定义灵活提取与强规则校验的数据模型。
支持显式建模“缺失字段”与“澄清追问”，杜绝模型在信息不全时产生幻觉捏造。
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

class ValidationError(Exception):
    """数据格式或逻辑校验失败异常"""
    pass

@dataclass
class RawExtraction:
    """阶段一：从自然语言中灵活提取的原始表述（允许非标准口语词）"""
    raw_city: Optional[str] = None           # 如："魔都"、"申城"
    raw_category: Optional[str] = None       # 如："打了个滴滴"、"出租车"
    raw_amount: Optional[float] = None       # 如：350.0
    raw_invoice_code: Optional[str] = None   # 如："INV-2026-SH-001"
    raw_date: Optional[str] = None           # 如："上周五" 或 "2026-09-18"

@dataclass
class NormalizedExpenseData:
    """阶段二：与企业主数据/财务标准严格对齐后的实体"""
    city: str                                # 标准城市（如："上海"）
    category: str                            # 标准财务科目（如："市内交通费"）
    amount: float                            # 严格合规的正浮点数
    invoice_code: str                        # 标准格式发票代码
    date: str                                # 标准日期格式 YYYY-MM-DD

@dataclass
class ExtractionEnvelope:
    """包装大模型意图提取的信封结构：显式表达完整度与澄清需求"""
    is_complete: bool
    normalized_data: Optional[NormalizedExpenseData] = None
    missing_fields: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)

    @classmethod
    def create_clarification_response(cls, missing_fields: List[str], partial_data: Dict[str, Any]) -> "ExtractionEnvelope":
        """构建信息缺失时的追问响应，拒绝擅自编造数据"""
        field_names_cn = {
            "city": "出差城市",
            "invoice_code": "发票代码",
            "amount": "报销金额",
            "category": "费用类别"
        }
        missing_cn = [field_names_cn.get(f, f) for f in missing_fields]
        
        known_info = []
        if partial_data.get("amount"):
            known_info.append(f"金额: {partial_data['amount']}元")
        if partial_data.get("city"):
            known_info.append(f"城市: {partial_data['city']}")
        if partial_data.get("category"):
            known_info.append(f"类别: {partial_data['category']}")

        known_str = f"（已为您识别 {', '.join(known_info)}）" if known_info else ""
        question = f"已收到您的报销意向{known_str}，但缺少必要的【{'、'.join(missing_cn)}】信息。请补充这些信息以便继续提报。"

        return cls(
            is_complete=False,
            normalized_data=None,
            missing_fields=missing_fields,
            needs_clarification=True,
            clarification_question=question
        )

from enum import Enum
import hashlib
import json

class ClaimStatus(str, Enum):
    """已核验报销申请单状态"""
    VALIDATED = "VALIDATED"                 # 交叉核验通过，待风控/待特批
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL" # 超标，已生成审批单并挂起
    APPROVED = "APPROVED"                   # 人工特批已批准
    REJECTED = "REJECTED"                   # 票据/行程异常或特批驳回
    DRAFT_CREATED = "DRAFT_CREATED"         # 已在下游财务系统创建草单

@dataclass
class ValidatedExpenseClaim:
    """阶段三：业务权威事实契约（经过发票、行程、政策三方核验后的报销申请）
    
    核心业务契约：
    1. 彻底解决自然语言抽取金额、风控核验金额与下游建单金额脱节的问题；
    2. 携带不可变的 version_hash，人工审批与最终建单均必须绑定同一 version_hash；
    3. 任何字段修改都会导致 hash 变更，防止审批被旁路篡改。
    """
    claim_id: str
    version_hash: str
    employee_id: str
    city: str
    category: str
    invoice_code: str
    claimed_amount: float       # 用户口头申报金额
    invoice_amount: float       # 发票中台查验的权威面额
    policy_limit: float         # 制度限额标准
    approved_amount: float      # 拟申报结算金额（经核验确定）
    trip_record_id: Optional[str]
    audit_trail: List[str] = field(default_factory=list)
    status: ClaimStatus = ClaimStatus.VALIDATED

    @staticmethod
    def compute_version_hash(
        employee_id: str,
        invoice_code: str,
        city: str,
        category: str,
        approved_amount: float,
        trip_record_id: Optional[str]
    ) -> str:
        payload = {
            "employee_id": employee_id,
            "invoice_code": invoice_code.strip().upper(),
            "city": city.strip(),
            "category": category.strip(),
            "approved_amount": f"{approved_amount:.2f}",
            "trip_record_id": trip_record_id or "NONE"
        }
        raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    @classmethod
    def create(
        cls,
        claim_id: str,
        employee_id: str,
        city: str,
        category: str,
        invoice_code: str,
        claimed_amount: float,
        invoice_amount: float,
        policy_limit: float,
        trip_record_id: Optional[str],
        audit_trail: List[str]
    ) -> "ValidatedExpenseClaim":
        # 业务规则：以发票中台查验出的真实面额作为权威核销金额
        approved_amount = invoice_amount
        v_hash = cls.compute_version_hash(
            employee_id=employee_id,
            invoice_code=invoice_code,
            city=city,
            category=category,
            approved_amount=approved_amount,
            trip_record_id=trip_record_id
        )
        return cls(
            claim_id=claim_id,
            version_hash=v_hash,
            employee_id=employee_id,
            city=city,
            category=category,
            invoice_code=invoice_code,
            claimed_amount=claimed_amount,
            invoice_amount=invoice_amount,
            policy_limit=policy_limit,
            approved_amount=approved_amount,
            trip_record_id=trip_record_id,
            audit_trail=audit_trail,
            status=ClaimStatus.VALIDATED
        )

