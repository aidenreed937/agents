"""标准企业财务数据资产 MCP Server (Model Context Protocol Server)
将企业内部的发票查验、OA行程匹配、制度检索和草单创建工具暴露为标准 MCP 协议服务。
使得企业核心能力与底层 Agent Runtime/Harness 彻底解耦，可被任何标准 MCP Client 即插即用挂载。
"""
import sys
import json
import asyncio
from typing import Dict, Any, List

from ..data_assets.invoice_center import InvoiceCenter
from ..data_assets.oa_trip_center import OATripCenter
from ..data_assets.policy_store import PolicyStore
from ..agent.tools import ExpenseTools
from ..governance.rbac import SecurityContext

# 定义标准 MCP 工具清单 (Tool Schemas)
MCP_TOOLS_SPEC = [
    {
        "name": "verify_invoice",
        "description": "向企业发票中台与税控系统查验发票真伪、面额、发生日期及去重状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_code": {
                    "type": "string",
                    "description": "发票唯一代码，如 INV-2026-901 或 INV-2026-SH-001"
                }
            },
            "required": ["invoice_code"]
        }
    },
    {
        "name": "query_approved_trip",
        "description": "向企业 OA 审批系统查询员工在特定日期和出差城市的有效审批出差单",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "员工工号，如 EMP-1001"},
                "date": {"type": "string", "description": "发生费用日期 (YYYY-MM-DD)"},
                "city": {"type": "string", "description": "出差目的城市，如 '北京' 或 '上海'"}
            },
            "required": ["employee_id", "date", "city"]
        }
    },
    {
        "name": "query_policy_limit",
        "description": "查询企业财务制度库中特定出差城市与费用类别的标准上限标准",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "出差城市"},
                "category": {"type": "string", "description": "费用类别，如 '市内交通费'、'住宿费'"}
            },
            "required": ["city", "category"]
        }
    },
    {
        "name": "create_expense_draft",
        "description": "在财务 ERP 预审系统中为员工创建报销草单（受控操作，仅限草单，严禁直接打款）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "报销员工工号"},
                "invoice_code": {"type": "string", "description": "关联发票代码"},
                "total_amount": {"type": "number", "description": "报销金额"},
                "destination": {"type": "string", "description": "出差城市"},
                "expense_type": {"type": "string", "description": "费用类别"},
                "idempotency_key": {"type": "string", "description": "业务唯一幂等防重键"}
            },
            "required": ["employee_id", "invoice_code", "total_amount", "idempotency_key"]
        }
    },
    {
        "name": "query_draft_by_idempotency_key",
        "description": "通过业务幂等键在财务系统反查已有草单（用于网络超时与系统崩溃恢复探查）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idempotency_key": {"type": "string", "description": "业务幂等键"}
            },
            "required": ["idempotency_key"]
        }
    }
]

class ExpenseMCPServer:
    """企业报销与资产中台标准 MCP 协议处理器"""

    def __init__(self, security_context: SecurityContext = None):
        self.ctx = security_context or SecurityContext.agent_system_context()

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回已注册的 MCP 工具规范列表"""
        return MCP_TOOLS_SPEC

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """根据标准 MCP JSON-RPC 调用分发至受控工具"""
        if tool_name == "verify_invoice":
            return ExpenseTools.query_invoice(arguments["invoice_code"], self.ctx)

        elif tool_name == "query_approved_trip":
            return ExpenseTools.query_trip(
                employee_id=arguments["employee_id"],
                date=arguments["date"],
                city=arguments["city"],
                ctx=self.ctx
            )

        elif tool_name == "query_policy_limit":
            return ExpenseTools.query_policy(
                city=arguments["city"],
                category=arguments["category"],
                ctx=self.ctx
            )

        elif tool_name == "create_expense_draft":
            idem_key = arguments.pop("idempotency_key", None)
            return ExpenseTools.create_reimbursement_draft(
                draft_data=arguments,
                idempotency_key=idem_key,
                ctx=self.ctx
            )

        elif tool_name == "query_draft_by_idempotency_key":
            res = ExpenseTools.query_draft_by_idempotency_key(arguments["idempotency_key"], self.ctx)
            return {"found": res is not None, "draft": res}

        else:
            raise ValueError(f"未知的 MCP 工具调用: {tool_name}")

    def handle_json_rpc(self, request_str: str) -> str:
        """处理符合 JSON-RPC 2.0 / MCP 标准的协议请求"""
        try:
            req = json.loads(request_str)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "tools/list":
                result = {"tools": self.list_tools()}
                return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                res = self.execute_tool(tool_name, arguments)
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, ensure_ascii=False)
                        }
                    ]
                }
                return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)

            else:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })

        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req.get("id") if "req" in locals() else None,
                "error": {"code": -32000, "message": str(e)}
            })

if __name__ == "__main__":
    # 支持作为标准 MCP Stdio Server 运行
    server = ExpenseMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = server.handle_json_rpc(line)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
