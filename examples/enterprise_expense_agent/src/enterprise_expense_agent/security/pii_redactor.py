"""Layer 1: 安全围栏与数据合规层 - 敏感个人信息（PII）脱敏与还原
在向大模型或公网传输前，将敏感数据（手机号、银行卡号、身份证号）脱敏为占位符；
在最终内部系统处理或展示时，安全解密还原，满足数据出境合规与安全防线。
"""
import re
from typing import Dict, Tuple

class PIIRedactor:
    """PII 敏感数据脱敏与还原中枢"""

    # 正则特征模式
    _PHONE_PATTERN = r"(1[3-9]\d{9})"
    _BANK_CARD_PATTERN = r"\b(62\d{14,17})\b"
    _ID_CARD_PATTERN = r"\b(\d{17}[\dXx])\b"

    @classmethod
    def redact(cls, text: str) -> Tuple[str, Dict[str, str]]:
        """
        前置脱敏：将敏感字符串替换为安全占位符，返回 (脱敏文本, 保险箱映射字典)
        """
        vault: Dict[str, str] = {}
        redacted_text = text

        # 1. 脱敏手机号
        def replace_phone(match):
            raw = match.group(1)
            token = f"[MASKED_PHONE_{len(vault)+1}]"
            vault[token] = raw
            return token

        redacted_text = re.sub(cls._PHONE_PATTERN, replace_phone, redacted_text)

        # 2. 脱敏银行卡
        def replace_bank_card(match):
            raw = match.group(1)
            token = f"[MASKED_CARD_{len(vault)+1}]"
            vault[token] = raw
            return token

        redacted_text = re.sub(cls._BANK_CARD_PATTERN, replace_bank_card, redacted_text)

        # 3. 脱敏身份证
        def replace_id_card(match):
            raw = match.group(1)
            token = f"[MASKED_IDCARD_{len(vault)+1}]"
            vault[token] = raw
            return token

        redacted_text = re.sub(cls._ID_CARD_PATTERN, replace_id_card, redacted_text)

        return redacted_text, vault

    @classmethod
    def restore(cls, text: str, vault: Dict[str, str]) -> str:
        """
        后置还原：将占位符安全替换回真实信息
        """
        restored = text
        for token, raw_val in vault.items():
            restored = restored.replace(token, raw_val)
        return restored

    # 别名支持
    unredact = restore
