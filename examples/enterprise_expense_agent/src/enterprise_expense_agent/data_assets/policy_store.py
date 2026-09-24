"""数据资产层：企业制度规则库
存储结构化的差旅报销标准、城市等级系数与特批审批层级规则。
"""
from typing import Dict, Any, Optional

# 结构化差旅制度标准库
_POLICY_STORE = {
    "上海": {
        "tier": "一线城市",
        "limits": {
            "市内交通费": 300.0,    # 单次市内打车上限 300 元
            "住宿费_每日": 600.0,
            "餐饮补贴_每日": 150.0
        },
        "overlimit_policy": {
            "allowed": True,
            "condition": "超出标准必须提交部门总监（DIRECTOR）进行合规特批，说明溢价原因",
            "approver_role": "DIRECTOR"
        }
    },
    "北京": {
        "tier": "一线城市",
        "limits": {
            "市内交通费": 300.0,    # 单次市内打车上限 300 元
            "住宿费_每日": 600.0,
            "餐饮补贴_每日": 150.0
        },
        "overlimit_policy": {
            "allowed": True,
            "condition": "超出标准必须提交部门总监特批",
            "approver_role": "DIRECTOR"
        }
    },
    "深圳": {
        "tier": "一线城市",
        "limits": {
            "市内交通费": 300.0,
            "住宿费_每日": 600.0,
            "餐饮补贴_每日": 150.0
        },
        "overlimit_policy": {
            "allowed": True,
            "condition": "超出标准必须提交部门总监特批",
            "approver_role": "DIRECTOR"
        }
    },
    "广州": {
        "tier": "一线城市",
        "limits": {
            "市内交通费": 300.0,
            "住宿费_每日": 600.0,
            "餐饮补贴": 300.0,
            "餐饮补贴_每日": 300.0
        },
        "overlimit_policy": {
            "allowed": True,
            "condition": "超出标准必须提交部门总监特批",
            "approver_role": "DIRECTOR"
        }
    },
    "杭州": {
        "tier": "新一线城市",
        "limits": {
            "市内交通费": 250.0,
            "住宿费_每日": 500.0,
            "餐饮补贴": 300.0,
            "餐饮补贴_每日": 300.0
        },
        "overlimit_policy": {
            "allowed": True,
            "condition": "超出标准必须提交部门总监特批",
            "approver_role": "DIRECTOR"
        }
    }
}


class PolicyStore:
    """企业制度数据资产接口"""

    @staticmethod
    def get_expense_limit(city: str, category: str) -> Dict[str, Any]:
        """
        获取指定城市特定类别的报销限额和超标审批政策
        :param city: 城市名称
        :param category: 费用类别
        :return: 政策信息
        """
        city_policy = _POLICY_STORE.get(city)
        if not city_policy:
            return {
                "found": False,
                "limit": 100.0,  # 默认二三线基准
                "overlimit_policy": None
            }
            
        limit = city_policy["limits"].get(category, 100.0)
        return {
            "found": True,
            "limit": limit,
            "overlimit_policy": city_policy["overlimit_policy"]
        }
