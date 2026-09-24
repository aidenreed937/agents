"""数据资产层：发票中台模拟组件
提供发票真伪查验、发票去重校验以及结构化票据信息。
"""
from typing import Dict, Any, Optional

# 模拟企业内部发票中台数据库
_MOCK_INVOICE_DATABASE = {
    "INV-2026-SH-001": {
        "invoice_code": "INV-2026-SH-001",
        "seller": "上海大众出租租赁有限公司",
        "amount": 350.0,
        "date": "2026-09-18",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,  # 尚未报销
    },
    "INV-2026-SH-999": {
        "invoice_code": "INV-2026-SH-999",
        "seller": "北京滴滴出行科技有限公司",
        "amount": 120.0,
        "date": "2026-08-10",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": True,   # 历史已被报销（用于测试查重拦截）
    },
    "INV-2026-901": {
        "invoice_code": "INV-2026-901",
        "seller": "北京首汽约车科技有限公司",
        "amount": 220.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-902": {
        "invoice_code": "INV-2026-902",
        "seller": "北京奇步天下科技有限公司",
        "amount": 180.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-905": {
        "invoice_code": "INV-2026-905",
        "seller": "北京首汽约车科技有限公司",
        "amount": 520.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-908": {
        "invoice_code": "INV-2026-908",
        "seller": "北京首汽约车科技有限公司",
        "amount": 160.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-BJ-HOTEL": {
        "invoice_code": "INV-2026-BJ-HOTEL",
        "seller": "北京丽思卡尔顿酒店有限公司",
        "amount": 650.0,
        "date": "2026-09-20",
        "category": "住宿费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-GZ-TAXI": {
        "invoice_code": "INV-2026-GZ-TAXI",
        "seller": "广州市白云出租汽车集团有限公司",
        "amount": 135.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-SZ-HOTEL": {
        "invoice_code": "INV-2026-SZ-HOTEL",
        "seller": "深圳华侨城大酒店有限公司",
        "amount": 800.0,
        "date": "2026-09-20",
        "category": "住宿费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-HZ-MEAL": {
        "invoice_code": "INV-2026-HZ-MEAL",
        "seller": "杭州知味观餐饮有限公司",
        "amount": 280.0,
        "date": "2026-09-20",
        "category": "餐饮补贴",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    },
    "INV-2026-REUSED-01": {
        "invoice_code": "INV-2026-REUSED-01",
        "seller": "上海锦江之星旅馆有限公司",
        "amount": 420.0,
        "date": "2026-08-15",
        "category": "住宿费",
        "is_valid_tax_code": True,
        "is_reimbursed": True,  # 历史已报销
    },
    "INV-2026-DIFF-01": {
        "invoice_code": "INV-2026-DIFF-01",
        "seller": "北京首汽约车科技有限公司",
        "amount": 260.0,
        "date": "2026-09-20",
        "category": "市内交通费",
        "is_valid_tax_code": True,
        "is_reimbursed": False,
    }
}



class InvoiceCenter:
    """发票数据资产服务接口"""

    @staticmethod
    def verify_and_get_invoice(invoice_code: str) -> Dict[str, Any]:
        """
        核验发票真伪及报销状态
        :param invoice_code: 发票唯一代码
        :return: 核验结果字典
        """
        invoice = _MOCK_INVOICE_DATABASE.get(invoice_code)
        if not invoice:
            return {
                "success": False,
                "error": f"发票代码 {invoice_code} 在国税发票库中未查到对应记录，疑似虚假发票",
                "invoice": None
            }
        
        if invoice["is_reimbursed"]:
            return {
                "success": False,
                "error": f"发票代码 {invoice_code} 在系统内已有历史报销记录，严禁重复报销",
                "invoice": invoice
            }
            
        return {
            "success": True,
            "error": None,
            "invoice": invoice
        }
