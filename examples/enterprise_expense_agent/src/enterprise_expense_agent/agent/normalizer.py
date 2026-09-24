"""语义归一化与数据对齐组件（Entity Normalizer）
负责两阶段处理的第二阶段：
将非结构化的自然语言提取项映射为企业内部的标准主数据枚举与财务科目字典。
"""
from typing import Optional, Tuple, Dict, Any, List
from .schema import RawExtraction, NormalizedExpenseData, ExtractionEnvelope, ValidationError

# 企业标准城市与别名词典
CITY_MAPPINGS: Dict[str, str] = {
    "上海": "上海",
    "魔都": "上海",
    "申城": "上海",
    "北京": "北京",
    "帝都": "北京",
    "广州": "广州",
    "羊城": "广州",
    "深圳": "深圳",
    "鹏城": "深圳",
    "杭州": "杭州",
    "钱塘": "杭州",
    "成都": "成都",
    "蓉城": "成都",
    "武汉": "武汉",
    "江城": "武汉",
}


# 财务会计科目与口语别名词典
CATEGORY_MAPPINGS: Dict[str, str] = {
    "市内交通费": "市内交通费",
    "打车": "市内交通费",
    "滴滴": "市内交通费",
    "打了个滴滴": "市内交通费",
    "出租车": "市内交通费",
    "网约车": "市内交通费",
    "住宿费": "住宿费",
    "酒店": "住宿费",
    "开房": "住宿费",
    "餐饮补贴": "餐饮补贴",
    "吃饭": "餐饮补贴",
    "餐费": "餐饮补贴"
}

class EntityNormalizer:
    """两阶段语义对齐与业务归一化服务"""

    @classmethod
    def normalize_city(cls, raw_city: Optional[str]) -> Optional[str]:
        if not raw_city:
            return None
        raw_clean = raw_city.strip()
        for alias, standard in CITY_MAPPINGS.items():
            if alias in raw_clean:
                return standard
        return raw_clean

    @classmethod
    def normalize_category(cls, raw_category: Optional[str]) -> Optional[str]:
        if not raw_category:
            return None
        raw_clean = raw_category.strip()
        for alias, standard in CATEGORY_MAPPINGS.items():
            if alias in raw_clean:
                return standard
        return raw_clean

    @classmethod
    def process(cls, raw: RawExtraction) -> ExtractionEnvelope:
        """
        核心对齐与校验流水线：
        1. 别名归一化（魔都 -> 上海，打了个滴滴 -> 市内交通费）
        2. 缺失字段审计（如果缺必要字段，显式构造追问信封，绝不脑补）
        3. 强类型业务约束（金额为正数、发票代码格式）
        """
        norm_city = cls.normalize_city(raw.raw_city)
        norm_category = cls.normalize_category(raw.raw_category)
        
        # 1. 检查必要字段完整性
        missing_fields: List[str] = []
        if not norm_city:
            missing_fields.append("city")
        if not raw.raw_amount:
            missing_fields.append("amount")
        if not raw.raw_invoice_code:
            missing_fields.append("invoice_code")
        if not norm_category:
            missing_fields.append("category")

        # 若关键字段缺失，直接终止并返回追问信封
        if missing_fields:
            partial_info = {
                "city": norm_city,
                "amount": raw.raw_amount,
                "category": norm_category,
                "invoice_code": raw.raw_invoice_code
            }
            return ExtractionEnvelope.create_clarification_response(missing_fields, partial_info)

        # 2. 强类型与业务规则校验
        validation_errors: List[str] = []
        if raw.raw_amount <= 0:
            validation_errors.append(f"报销金额必须为大于 0 的有效数值，当前提取为: {raw.raw_amount}")

        if not raw.raw_invoice_code.startswith("INV-"):
            validation_errors.append(f"发票代码格式不规范（必须以 INV- 开头），当前提取为: {raw.raw_invoice_code}")

        if validation_errors:
            return ExtractionEnvelope(
                is_complete=False,
                validation_errors=validation_errors,
                needs_clarification=True,
                clarification_question=f"提取到的数据未能通过业务格式校验: {'; '.join(validation_errors)}"
            )

        # 3. 校验通过，构建规范化实体
        standard_date = raw.raw_date if raw.raw_date else "2026-09-18"
        normalized_data = NormalizedExpenseData(
            city=norm_city,
            category=norm_category,
            amount=round(float(raw.raw_amount), 2),
            invoice_code=raw.raw_invoice_code.strip(),
            date=standard_date
        )

        return ExtractionEnvelope(
            is_complete=True,
            normalized_data=normalized_data,
            needs_clarification=False
        )
