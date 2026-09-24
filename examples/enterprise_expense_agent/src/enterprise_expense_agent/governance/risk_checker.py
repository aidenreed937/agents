"""业务治理层：合规风控规则引擎
自动比对数据资产，执行反欺诈、行程真实性检验、限额超标计算，确定是否需要人工介入。
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class RiskAssessment:
    """风控评估报告"""
    is_passed: bool
    risk_level: str          # "LOW", "MEDIUM", "HIGH"
    overlimit_amount: float  # 超标金额
    policy_limit: float      # 制度限额
    requires_hitl: bool      # 是否必须触发人在回路（人工介入）
    reasons: List[str] = field(default_factory=list)

class RiskChecker:
    """业务风控规则检查器"""

    @staticmethod
    def evaluate(invoice_res: Dict[str, Any], 
                 trip_res: Dict[str, Any], 
                 policy_res: Dict[str, Any]) -> RiskAssessment:
        reasons = []
        requires_hitl = False
        risk_level = "LOW"
        overlimit_amount = 0.0

        # 1. 票据合规核验
        if not invoice_res["success"]:
            reasons.append(f"发票异常: {invoice_res['error']}")
            return RiskAssessment(
                is_passed=False,
                risk_level="HIGH",
                overlimit_amount=0.0,
                policy_limit=0.0,
                requires_hitl=False,
                reasons=reasons
            )

        invoice_data = invoice_res["invoice"]

        # 2. 行程真实性核验
        if not trip_res["matched"]:
            reasons.append(f"行程异常: {trip_res['error']}")
            return RiskAssessment(
                is_passed=False,
                risk_level="HIGH",
                overlimit_amount=0.0,
                policy_limit=0.0,
                requires_hitl=False,
                reasons=reasons
            )

        # 3. 制度限额核验
        policy_limit = policy_res.get("limit", 200.0)
        actual_amount = invoice_data["amount"]

        if actual_amount > policy_limit:
            overlimit_amount = actual_amount - policy_limit
            risk_level = "MEDIUM"
            requires_hitl = True
            reasons.append(
                f"费用超标: 单次申报金额 {actual_amount} 元，超出当前城市标准上限 {policy_limit} 元（超标 {overlimit_amount} 元）。"
                f"根据制度规定，必须经由部门总监特批！"
            )
        else:
            reasons.append("费用合规: 发票真实有效、出差行程匹配且金额在制度限额范围内。")

        return RiskAssessment(
            is_passed=True,
            risk_level=risk_level,
            overlimit_amount=overlimit_amount,
            policy_limit=policy_limit,
            requires_hitl=requires_hitl,
            reasons=reasons
        )
