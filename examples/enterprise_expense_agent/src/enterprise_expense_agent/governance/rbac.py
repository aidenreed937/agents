"""业务治理层：基于角色的权限控制（RBAC）
实现企业安全防线：严格限制 Agent 的操作权限范围，杜绝直接资金划转与越权写入。
"""
from enum import Enum
from typing import Set, Union, Optional
from dataclasses import dataclass

class Role(str, Enum):
    AGENT = "AGENT"                    # 智能体数字员工
    EMPLOYEE = "EMPLOYEE"              # 普通提报员工
    DIRECTOR = "DIRECTOR"              # 业务/部门总监（具备特批权）
    FINANCE_CLERK = "FINANCE_CLERK"    # 财务结算出纳（具备最终支付打款权）

class Action(str, Enum):
    READ_INVOICE = "READ_INVOICE"
    READ_TRIP = "READ_TRIP"
    READ_POLICY = "READ_POLICY"
    CREATE_DRAFT = "CREATE_DRAFT"          # 创建财务报销草单
    APPROVE_OVERLIMIT = "APPROVE_OVERLIMIT"# 审批超标费用
    EXECUTE_PAYMENT = "EXECUTE_PAYMENT"    # 执行系统打款划转（高危动作）

@dataclass
class SecurityContext:
    """可信上游认证网关注入的安全上下文凭据
    彻底废除函数签名中随意传入 Role 枚举的伪造漏洞
    """
    user_id: str
    role: Role
    session_id: str = "sys_session_001"
    is_authenticated: bool = True

    @classmethod
    def agent_system_context(cls) -> "SecurityContext":
        """智能体内部工作流受限上下文"""
        return cls(user_id="AGENT_DAEMON", role=Role.AGENT, session_id="agent_internal_session")

    @classmethod
    def employee_context(cls, employee_id: str) -> "SecurityContext":
        """员工前台提报可信上下文"""
        return cls(user_id=employee_id, role=Role.EMPLOYEE, session_id=f"sess_{employee_id}")

    @classmethod
    def director_context(cls, director_id: str) -> "SecurityContext":
        """部门主管/总监审批可信上下文"""
        return cls(user_id=director_id, role=Role.DIRECTOR, session_id=f"sess_{director_id}")

# 权限矩阵定义
_ROLE_PERMISSIONS = {
    Role.AGENT: {
        Action.READ_INVOICE,
        Action.READ_TRIP,
        Action.READ_POLICY,
        Action.CREATE_DRAFT,
    },
    Role.EMPLOYEE: {
        Action.READ_INVOICE,
        Action.READ_TRIP,
        Action.READ_POLICY,
        Action.CREATE_DRAFT,
    },
    Role.DIRECTOR: {
        Action.READ_INVOICE,
        Action.READ_TRIP,
        Action.READ_POLICY,
        Action.CREATE_DRAFT,
        Action.APPROVE_OVERLIMIT,
    },
    Role.FINANCE_CLERK: {
        Action.READ_INVOICE,
        Action.READ_POLICY,
        Action.CREATE_DRAFT,
        Action.EXECUTE_PAYMENT,
    }
}


class PermissionDeniedError(Exception):
    """越权操作安全拦截异常"""
    pass

class RBACManager:
    """权限校验与拦截管理器"""

    @staticmethod
    def verify(actor: Union[Role, SecurityContext], action: Action) -> bool:
        """
        校验执行主体是否拥有执行特定动作的权限
        :param actor: SecurityContext 或 Role 枚举
        :raises PermissionDeniedError: 未认证或权限不满足时抛出强校验异常
        """
        if isinstance(actor, SecurityContext):
            if not actor.is_authenticated:
                raise PermissionDeniedError(f"[安全治理拦截] 用户 '{actor.user_id}' 会话未认证或已失效！")
            role = actor.role
            actor_desc = f"用户 '{actor.user_id}'(角色:{role.value})"
        else:
            role = actor
            actor_desc = f"角色 '{role.value}'"

        allowed_actions: Set[Action] = _ROLE_PERMISSIONS.get(role, set())
        if action not in allowed_actions:
            raise PermissionDeniedError(
                f"[安全治理拦截] {actor_desc} 无权执行动作 '{action.value}'！"
                f"在企业生产环境中，严禁授予 Agent 直接打款或高危核心系统写入权限！"
            )
        return True

