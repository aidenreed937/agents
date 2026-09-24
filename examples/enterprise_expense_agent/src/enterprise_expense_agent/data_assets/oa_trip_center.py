"""数据资产层：OA 差旅中台模拟组件
提供出差申请单核验、行程目的地与起止日期校验。
"""
from typing import Dict, Any, List, Optional

# 模拟企业 OA 流程中的出差审批记录
_MOCK_TRIP_DATABASE = {
    "EMP_1001": [
        {
            "trip_id": "TRIP-202609-088",
            "employee_id": "EMP-1001",
            "employee_name": "张三",
            "department": "技术研发部",
            "destination_city": "上海",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "拜访华东重要金融客户技术交流"
        },
        {
            "trip_id": "TRIP-202609-089",
            "employee_id": "EMP-1001",
            "employee_name": "张三",
            "department": "技术研发部",
            "destination_city": "北京",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "北京总部架构委员会技术交流"
        }
    ],
    "EMP_1002": [
        {
            "trip_id": "TRIP-202609-090",
            "employee_id": "EMP-1002",
            "employee_name": "李四",
            "department": "市场销售部",
            "destination_city": "北京",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "客户签约"
        }
    ],
    "EMP_1006": [
        {
            "trip_id": "TRIP-202609-091",
            "employee_id": "EMP-1006",
            "employee_name": "赵六",
            "department": "业务拓展部",
            "destination_city": "深圳",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "深圳出差"
        }
    ],
    "EMP_1007": [
        {
            "trip_id": "TRIP-202609-092",
            "employee_id": "EMP-1007",
            "employee_name": "王七",
            "department": "基础架构部",
            "destination_city": "北京",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "北京数据中心巡检"
        }
    ],
    "EMP_1008": [
        {
            "trip_id": "TRIP-202609-098",
            "employee_id": "EMP-1008",
            "employee_name": "钱八",
            "department": "技术支持部",
            "destination_city": "北京",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "现场系统部署支持"
        }
    ],
    "EMP_1010": [
        {
            "trip_id": "TRIP-202609-101",
            "employee_id": "EMP-1010",
            "employee_name": "周十",
            "department": "市场拓展部",
            "destination_city": "广州",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "广州大客户拜访"
        }
    ],
    "EMP_1011": [
        {
            "trip_id": "TRIP-202609-102",
            "employee_id": "EMP-1011",
            "employee_name": "吴十一",
            "department": "华南大区",
            "destination_city": "深圳",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "深圳研发中心技术交流"
        }
    ],
    "EMP_1012": [
        {
            "trip_id": "TRIP-202609-103",
            "employee_id": "EMP-1012",
            "employee_name": "郑十二",
            "department": "华东大区",
            "destination_city": "杭州",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "approval_status": "APPROVED",
            "purpose": "杭州电商峰会技术参会"
        }
    ]
}



class OATripCenter:
    """OA 差旅数据资产服务接口"""

    @staticmethod
    def query_approved_trip(employee_id: str, date: str, city: str) -> Dict[str, Any]:
        """
        查询员工指定日期和城市的出差审批记录
        :param employee_id: 员工工号
        :param date: 发生费用日期 (YYYY-MM-DD)
        :param city: 发生费用城市
        :return: 核验结果
        """
        normalized_emp_id = employee_id.replace("-", "_").upper()
        trips = _MOCK_TRIP_DATABASE.get(normalized_emp_id, [])
        for trip in trips:
            if (trip["approval_status"] == "APPROVED" and 
                trip["destination_city"] == city and 
                trip["start_date"] <= date <= trip["end_date"]):
                return {
                    "matched": True,
                    "trip": trip,
                    "error": None
                }
                
        return {
            "matched": False,
            "trip": None,
            "error": f"在 OA 系统中未检索到员工 {employee_id} 于 {date} 在 {city} 的有效已审批差旅申请单"
        }
