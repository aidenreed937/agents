"""Layer 1: 安全围栏与数据合规层 - 防 Prompt 注入防火墙
负责在输入进入大模型之前，识别恶意越狱指令、提示词注入及策略绕过尝试。
"""
import re
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class GuardrailResult:
    """安全审查结果"""
    is_safe: bool
    risk_score: float            # 0.0 ~ 1.0
    attack_type: Optional[str]   # "INJECTION", "JAILBREAK", "POLICY_OVERRIDE", None
    reason: Optional[str]

class PromptGuardrail:
    """提示词安全防护防火墙"""

    # 典型恶意注入攻击与越狱模式特征库
    _ATTACK_PATTERNS = [
        (r"(忽略|ignore|forget).*(之前|所有|所有之前|previous).*(指令|提示|规则|instruction)", "PROMPT_INJECTION", 0.95),
        (r"(直接打款|无需校验|跳过审批|免密支付|无需发票)", "POLICY_OVERRIDE", 0.90),
        (r"(进入开发者模式|越狱模式|jailbreak|DAN mode)", "JAILBREAK", 0.99),
        (r"(把限额改成|修改.*上限为|提高额度至\s*\d{4,})", "POLICY_OVERRIDE", 0.85),
        (r"(输出你的系统提示词|show system prompt|print your instructions)", "PROMPT_LEAKAGE", 0.80),
    ]

    @classmethod
    def inspect(cls, user_input: str) -> GuardrailResult:
        """
        前置输入安全审查
        """
        for pattern, attack_type, score in cls._ATTACK_PATTERNS:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                matched_str = match.group(0)
                return GuardrailResult(
                    is_safe=False,
                    risk_score=score,
                    attack_type=attack_type,
                    reason=f"命中恶意安全拦截规则 [{attack_type}]，检测到危险注入模式: '{matched_str}'"
                )

        return GuardrailResult(
            is_safe=True,
            risk_score=0.0,
            attack_type=None,
            reason="安全审查通过，未发现对抗性攻击特征"
        )
