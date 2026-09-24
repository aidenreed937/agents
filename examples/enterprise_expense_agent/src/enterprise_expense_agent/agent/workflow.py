"""智能体工作流与状态机编排（Enterprise Expense Workflow / LangGraph StateGraph）
工业级落地架构核心流程：
自然语言申报 → 结构化提取 → 业务事实核验 (发票/行程/政策交叉比对) → 形成不可变已核验申请契约 (ValidatedExpenseClaim) 
→ 确定性合规风控 → 必要时人在回路特批 (LangGraph 原生 interrupt 强绑定版本哈希) → 两阶段幂等草单建单闭环。

本模块完全基于 LangGraph StateGraph 原生编译与调度：
1. 节点（Nodes）遵循纯函数/契约变换设计；
2. 条件边（Conditional Edges）实现外部规则绝对受控路由；
3. 人在回路（HITL）采用 LangGraph 原生 `interrupt()` 与 `Command(resume=...)` 机制；
4. 运行状态与历史通道（Channels）交由 LangGraphCheckpointer 统一托管与持久化。
"""
import time
import asyncio
from typing import Dict, Any, Optional, Union, Sequence, List

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.base import BaseCheckpointSaver

from .state import ExpenseAgentState
from .tools import ExpenseTools
from .schema import RawExtraction, ExtractionEnvelope, ValidatedExpenseClaim, ClaimStatus
from .normalizer import EntityNormalizer
from .router import ModelRouter
from .checkpointer import LangGraphFileCheckpointer, LocalCheckpointer
from ..config.prompt_registry import PromptRegistry
from ..security.guardrail import PromptGuardrail
from ..security.pii_redactor import PIIRedactor
from ..governance.risk_checker import RiskChecker
from ..governance.hitl import HITLManager, Role
from ..governance.rbac import SecurityContext
from ..governance.idempotency import IdempotencyManager

class EnterpriseExpenseWorkflow:
    """企业级差旅报销智能体状态机（LangGraph 编排受控落地版）"""

    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        idempotency_manager: Optional[IdempotencyManager] = None,
        prompt_registry: Optional[PromptRegistry] = None,
    ):
        self.hitl_manager = HITLManager()
        self.checkpointer = checkpointer or LangGraphFileCheckpointer()
        self.idempotency_manager = idempotency_manager or IdempotencyManager()
        self.prompt_registry = prompt_registry or PromptRegistry()

        # 构建并编译 LangGraph 状态图
        self._builder = StateGraph(ExpenseAgentState)
        self._build_graph()
        self.graph = self._builder.compile(checkpointer=self.checkpointer)

    # ---------------- 节点 1: 安全防护与 PII 隐私脱敏 ----------------
    def node_security_guardrail(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Security_Layer", "安全层启动：执行 PII 敏感脱敏与防注入防火墙审查...")

        # 1. PII 敏感信息前置脱敏
        redacted_text, vault = PIIRedactor.redact(state.raw_user_input)
        state.redacted_input = redacted_text
        state.pii_vault = vault
        if vault:
            state.log_step(
                "Security_Layer",
                f"【PII 数据脱敏】已识别并掩码 {len(vault)} 处隐私项（手机/卡号/身份证），保存在本地安全保险箱。"
            )

        # 2. 防注入与越狱安全审查
        guard_res = PromptGuardrail.inspect(redacted_text)
        if not guard_res.is_safe:
            state.guardrail_blocked = True
            state.guardrail_attack_type = guard_res.attack_type
            state.guardrail_reason = guard_res.reason
            state.status = "REJECTED_GUARDRAIL"
            state.error = f"安全防护网拦截：检测到恶意攻击行为 [{guard_res.attack_type}]，理由: {guard_res.reason}"
            state.log_step("Security_Layer", f"【高危阻断】{state.error}")
            return state

        state.log_step("Security_Layer", "安全防火墙检查通过：未发现注入、越狱或提示词泄露风险。")
        return state

    # ---------------- 节点 2: 意图理解与单模型结构化提取 ----------------
    def node_parse_intent(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Model_Extraction", "模型层启动：加载版本化 Prompt 模板并执行单模型要素抽取...")

        # 1. 读取版本化提示词
        sys_prompt = self.prompt_registry.get("system_prompt", version=state.prompt_version)
        state.log_step("Model_Extraction", f"载入 Prompt 模板版本: [{state.prompt_version}]")

        # 2. 单一确定模型要素抽取
        query_input = state.redacted_input or state.raw_user_input
        raw_extraction, model_used, cost_ratio = ModelRouter.extract(query_input)
        state.model_used = model_used
        state.token_cost_ratio = cost_ratio
        state.log_step(
            "Model_Extraction",
            f"模型抽取执行完成，使用基线模型: [{model_used}]"
        )

        # 3. 实体归一化与缺失项审计
        envelope = EntityNormalizer.process(raw_extraction)

        if envelope.needs_clarification:
            state.status = "WAITING_CLARIFICATION"
            state.needs_clarification = True
            state.clarification_question = envelope.clarification_question
            state.missing_fields = envelope.missing_fields
            state.log_step(
                "Model_Extraction",
                f"【平衡机制生效】识别到输入缺少关键字段 {envelope.missing_fields}，"
                f"拒绝擅自脑补！已触发反问追问。"
            )
            return state

        norm = envelope.normalized_data
        state.extracted_data = {
            "city": norm.city,
            "category": norm.category,
            "amount": norm.amount,
            "invoice_code": norm.invoice_code,
            "date": norm.date,
            "user_claim_reason": query_input
        }
        state.log_step(
            "Model_Extraction",
            f"语义对齐完成 -> 城市: '{norm.city}', 科目: '{norm.category}', "
            f"口头申报金额: {norm.amount}元, 发票代码: {norm.invoice_code}"
        )
        return state

    # ---------------- 节点 3: 数据资产中台层 (异步高并发 I/O) ----------------
    async def node_fetch_data_assets(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Data_Assets", "数据中台层启动：并行检索发票中台、OA行程与政策知识库...")

        ext = state.extracted_data
        t0 = time.perf_counter()

        # 并发执行 3 项独立的 I/O 查询
        invoice_res, trip_res, policy_res = await asyncio.gather(
            ExpenseTools.async_query_invoice(ext["invoice_code"], state.security_context),
            ExpenseTools.async_query_trip(state.employee_id, ext["date"], ext["city"], state.security_context),
            ExpenseTools.async_query_policy(ext["city"], ext["category"], state.security_context)
        )

        io_duration = (time.perf_counter() - t0) * 1000
        state.io_duration_ms = io_duration
        state.invoice_data = invoice_res
        state.trip_data = trip_res
        state.policy_data = policy_res

        state.log_step(
            "Data_Assets",
            f"3 项数据中台并行检索完成！耗时: {io_duration:.2f}ms。"
            f"发票有效={invoice_res.get('success')}, 行程匹配={trip_res.get('matched')}, 制度上限={policy_res.get('limit')}元"
        )
        return state

    # ---------------- 节点 4: 业务事实交叉核验与权威契约固化 ----------------
    def node_cross_validate_claim(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Cross_Validation", "业务核验启动：比对口头申报与发票票面、出差审批事实...")
        ext = state.extracted_data
        inv_res = state.invoice_data or {}
        trip_res = state.trip_data or {}
        policy_res = state.policy_data or {}

        audit_trail = []

        # 1. 票据真实性校验
        if not inv_res.get("success"):
            error_reason = inv_res.get("error", "发票查验失败")
            state.status = "FAILED"
            state.error = f"票据核验未通过: {error_reason}"
            state.log_step("Cross_Validation", f"【核验失败】{state.error}")
            return state

        invoice = inv_res["invoice"]
        claimed_amt = ext["amount"]
        actual_inv_amt = float(invoice["amount"])

        # 2. 金额一致性核对
        if abs(claimed_amt - actual_inv_amt) > 0.01:
            audit_trail.append(
                f"金额校正：口头申报金额 ({claimed_amt}元) 与发票权威票面金额 ({actual_inv_amt}元) 不一致，"
                f"自动以税控发票实际面额 {actual_inv_amt}元 为权威入账基准。"
            )
            state.log_step("Cross_Validation", audit_trail[-1])
        else:
            audit_trail.append(f"金额一致：申报金额与发票票面金额完全一致 ({actual_inv_amt}元)。")

        # 3. 行程真实性校验
        trip_record_id = None
        if not trip_res.get("matched"):
            error_reason = trip_res.get("error", "无匹配的出差申请")
            state.status = "FAILED"
            state.error = f"行程核验未通过: {error_reason}"
            state.log_step("Cross_Validation", f"【核验失败】{state.error}")
            return state
        else:
            trip_info = trip_res.get("trip", {})
            trip_record_id = trip_info.get("trip_id")
            audit_trail.append(f"行程匹配：关联到已审批的出差行程单 [{trip_record_id}]。")

        # 4. 政策额度固化
        policy_limit = float(policy_res.get("limit", 200.0))
        audit_trail.append(f"政策基准：{ext['city']} {ext['category']} 制度上限为 {policy_limit}元/天。")

        # 5. 生成权威不可变申请契约 ValidatedExpenseClaim
        claim_id = f"CLAIM-EXP-{state.employee_id[-4:]}-{int(time.time())}"
        validated_claim = ValidatedExpenseClaim.create(
            claim_id=claim_id,
            employee_id=state.employee_id,
            city=ext["city"],
            category=ext["category"],
            invoice_code=ext["invoice_code"],
            claimed_amount=claimed_amt,
            invoice_amount=actual_inv_amt,
            policy_limit=policy_limit,
            trip_record_id=trip_record_id,
            audit_trail=audit_trail
        )
        state.validated_claim = validated_claim
        state.log_step(
            "Cross_Validation",
            f"权威报销契约已固化 [{claim_id}]！版本指纹 Hash: [{validated_claim.version_hash[:12]}...]，"
            f"权威结算金额: {validated_claim.approved_amount}元。"
        )
        return state

    # ---------------- 节点 5: 确定性风控规则评估 ----------------
    def node_governance_check(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Governance_Engine", "风控引擎启动：基于权威契约评估合规性与超标测算...")
        assessment = RiskChecker.evaluate(
            state.invoice_data,
            state.trip_data,
            state.policy_data
        )
        state.risk_assessment = assessment

        for reason in assessment.reasons:
            state.log_step("Governance_Engine", f"规则判定: {reason}")

        return state

    # ---------------- 节点 6: 人在回路特批工单生成与现场快照 ----------------
    def node_prepare_hitl(self, state: ExpenseAgentState) -> ExpenseAgentState:
        claim = state.validated_claim
        state.log_step("HITL_Interrupt", "检测到费用超标，状态机生成特批工单并准备触发 [interrupt] 挂起...")

        ticket = self.hitl_manager.create_interrupt_ticket(
            employee_id=state.employee_id,
            amount=claim.approved_amount,
            overlimit_amount=state.risk_assessment.overlimit_amount,
            reason="; ".join(state.risk_assessment.reasons),
            claim_id=claim.claim_id,
            claim_version_hash=claim.version_hash
        )
        claim.status = ClaimStatus.REQUIRES_APPROVAL
        state.hitl_ticket = ticket
        state.status = "PAUSED_HITL"
        state.log_step(
            "HITL_Interrupt",
            f"已生成特批工单 [{ticket.ticket_id}]，强绑定单据版本 [{claim.version_hash[:12]}...]。"
        )
        return state

    # ---------------- 节点 7: LangGraph 原生断点挂起与恢复接入 ----------------
    def node_wait_for_hitl(self, state: ExpenseAgentState) -> ExpenseAgentState:
        ticket = state.hitl_ticket
        claim = state.validated_claim
        state.log_step("HITL_Interrupt", f"LangGraph 原生 [interrupt] 生效，线程 [{state.thread_id}] 挂起，等待人工特批。")

        # 触发 LangGraph 原生断点挂起
        decision = interrupt({
            "ticket_id": ticket.ticket_id,
            "claim_id": claim.claim_id,
            "claim_version_hash": claim.version_hash,
            "overlimit_amount": state.risk_assessment.overlimit_amount,
            "reason": ticket.reason
        })

        # 外部调用 Command(resume=...) 唤醒恢复执行
        approver = decision.get("operator")
        approved = decision.get("approved", False)
        comment = decision.get("comment", "")
        approver_desc = approver.user_id if isinstance(approver, SecurityContext) else (approver.value if hasattr(approver, "value") else str(approver))

        state.log_step("HITL_Resume", f"收到审批人回调: 主体={approver_desc}, 是否同意={approved}, 批语={comment}")

        # 登记工单并执行授权与契约版本验签
        self.hitl_manager.register_ticket(ticket)
        self.hitl_manager.submit_decision(
            ticket_id=ticket.ticket_id,
            operator=approver,
            is_approved=approved,
            comment=comment,
            expected_version_hash=claim.version_hash
        )

        if approved:
            state.validated_claim.status = ClaimStatus.APPROVED
            state.status = "APPROVED"
            state.log_step("HITL_Resume", "总监特批通过，申请版本校验一致，进入草单生成环节。")
        else:
            state.validated_claim.status = ClaimStatus.REJECTED
            state.status = "REJECTED"
            state.log_step("HITL_Resume", "总监驳回超标申请，报销流程终止。")

        return state

    # ---------------- 节点 8: 两阶段幂等防重与最终草单闭环 ----------------
    def node_create_draft(self, state: ExpenseAgentState) -> ExpenseAgentState:
        state.log_step("Draft_Generator", "建单引擎启动：执行两阶段幂等检测并创建预审草单...")

        claim = state.validated_claim
        idem_key = IdempotencyManager.generate_key_from_version_hash(
            user_id=state.employee_id,
            version_hash=claim.version_hash
        )
        state.idempotency_key = idem_key

        # 1. 探查下游财务系统是否已存在对应草单
        existing_draft = ExpenseTools.query_draft_by_idempotency_key(idem_key, state.security_context)
        if existing_draft:
            state.is_idempotent_duplicate = True
            state.reimbursement_draft = existing_draft
            state.status = "COMPLETED"
            claim.status = ClaimStatus.DRAFT_CREATED
            state.log_step(
                "Draft_Generator",
                f"【幂等反查命中】下游系统已存在单据 [{existing_draft['draft_id']}]，直接安全复用！"
            )
            return state

        # 2. 检查本地幂等锁
        is_new, prev_result = self.idempotency_manager.check_or_lock(idem_key)
        if not is_new and prev_result:
            state.is_idempotent_duplicate = True
            state.reimbursement_draft = prev_result
            state.status = "COMPLETED"
            claim.status = ClaimStatus.DRAFT_CREATED
            state.log_step(
                "Draft_Generator",
                f"【本地幂等命中】检测到重复提交！直接返回历史草单 [{prev_result['draft_id']}]。"
            )
            return state

        # 3. 首次调用外部财务系统创建草单
        draft_payload = {
            "employee_id": claim.employee_id,
            "claim_id": claim.claim_id,
            "claim_version_hash": claim.version_hash,
            "invoice_code": claim.invoice_code,
            "total_amount": claim.approved_amount,
            "base_amount": claim.policy_limit,
            "overlimit_approved_amount": state.risk_assessment.overlimit_amount if state.risk_assessment else 0.0,
            "approver_comment": state.hitl_ticket.comment if state.hitl_ticket else "标准额度内系统直通",
            "destination": claim.city,
            "expense_type": claim.category,
            "audit_trail": claim.audit_trail
        }

        draft_res = ExpenseTools.create_reimbursement_draft(
            draft_data=draft_payload,
            idempotency_key=idem_key,
            ctx=state.security_context
        )

        # 4. 固化本地幂等结果并完成流转
        self.idempotency_manager.mark_completed(idem_key, draft_res)
        state.reimbursement_draft = draft_res
        claim.status = ClaimStatus.DRAFT_CREATED
        state.status = "COMPLETED"
        state.log_step(
            "Draft_Generator",
            f"财务预审单已成功建立 [{draft_res['draft_id']}]，入账金额: {claim.approved_amount}元，"
            f"业务幂等键已固化 [{idem_key[:12]}...]。"
        )
        return state

    # ---------------- 路由分支判定条件 ----------------
    @staticmethod
    def _route_after_guardrail(state: ExpenseAgentState):
        if state.guardrail_blocked or state.status == "REJECTED_GUARDRAIL":
            return END
        return "parse_intent"

    @staticmethod
    def _route_after_intent(state: ExpenseAgentState):
        if state.status == "WAITING_CLARIFICATION":
            return END
        return "fetch_data_assets"

    @staticmethod
    def _route_after_cross_validate(state: ExpenseAgentState):
        if state.status == "FAILED":
            return END
        return "governance_check"

    @staticmethod
    def _route_after_governance(state: ExpenseAgentState):
        if not state.risk_assessment.is_passed:
            state.status = "FAILED"
            state.error = "风险拦截：" + "; ".join(state.risk_assessment.reasons)
            return END
        if state.risk_assessment.requires_hitl:
            return "prepare_hitl"
        return "create_draft"

    @staticmethod
    def _route_after_hitl(state: ExpenseAgentState):
        if state.status == "APPROVED":
            return "create_draft"
        return END

    # ---------------- 组装 LangGraph 图拓扑 ----------------
    def _build_graph(self):
        # 1. 注册节点
        self._builder.add_node("security_guardrail", self.node_security_guardrail)
        self._builder.add_node("parse_intent", self.node_parse_intent)
        self._builder.add_node("fetch_data_assets", self.node_fetch_data_assets)
        self._builder.add_node("cross_validate_claim", self.node_cross_validate_claim)
        self._builder.add_node("governance_check", self.node_governance_check)
        self._builder.add_node("prepare_hitl", self.node_prepare_hitl)
        self._builder.add_node("wait_for_hitl", self.node_wait_for_hitl)
        self._builder.add_node("create_draft", self.node_create_draft)

        # 2. 注册控制流与条件边
        self._builder.add_edge(START, "security_guardrail")
        self._builder.add_conditional_edges(
            "security_guardrail",
            self._route_after_guardrail,
            {"parse_intent": "parse_intent", END: END}
        )
        self._builder.add_conditional_edges(
            "parse_intent",
            self._route_after_intent,
            {"fetch_data_assets": "fetch_data_assets", END: END}
        )
        self._builder.add_edge("fetch_data_assets", "cross_validate_claim")
        self._builder.add_conditional_edges(
            "cross_validate_claim",
            self._route_after_cross_validate,
            {"governance_check": "governance_check", END: END}
        )
        self._builder.add_conditional_edges(
            "governance_check",
            self._route_after_governance,
            {"prepare_hitl": "prepare_hitl", "create_draft": "create_draft", END: END}
        )
        self._builder.add_edge("prepare_hitl", "wait_for_hitl")
        self._builder.add_conditional_edges(
            "wait_for_hitl",
            self._route_after_hitl,
            {"create_draft": "create_draft", END: END}
        )
        self._builder.add_edge("create_draft", END)

    def _convert_result_to_state(self, res: Dict[str, Any]) -> ExpenseAgentState:
        return ExpenseAgentState.from_langgraph(res)

    # ---------------- 状态机运行主调度入口 ----------------
    async def run(self, initial_state: ExpenseAgentState) -> ExpenseAgentState:
        initial_state.log_step("Workflow", f">>> 开始执行企业级报销工作流 [Thread: {initial_state.thread_id}] <<<")
        config = {"configurable": {"thread_id": initial_state.thread_id}}
        res = await self.graph.ainvoke(initial_state, config=config)
        return self._convert_result_to_state(res)

    # ---------------- 人在回路恢复接口（支持跨进程冷启动恢复与契约验签） ----------------
    def resume_after_hitl(
        self,
        thread_id: str,
        approver: Union[Role, SecurityContext],
        approved: bool,
        comment: str,
        in_memory_state: Optional[ExpenseAgentState] = None
    ) -> ExpenseAgentState:
        """从挂起状态恢复执行：
        1. 自动支持冷启动从磁盘检查点恢复；
        2. 校验审批人权限（SecurityContext 优先）；
        3. 强校验审批工单绑定的 claim_version_hash，杜绝旁路数据篡改；
        4. 审批批准后，按原申请版本继续完成草单建单。
        """
        config = {"configurable": {"thread_id": thread_id}}

        if in_memory_state is not None:
            self.graph.update_state(config, in_memory_state.to_dict())

        payload = {
            "operator": approver,
            "approved": approved,
            "comment": comment
        }

        # 通过 LangGraph Command(resume=...) 唤醒处于 wait_for_hitl 的节点
        res = self.graph.invoke(Command(resume=payload), config=config)
        state = self._convert_result_to_state(res)

        # 流程完结后安全清理检查点
        if hasattr(self.checkpointer, "delete_thread"):
            self.checkpointer.delete_thread(thread_id)

        return state

    async def aresume_after_hitl(
        self,
        thread_id: str,
        approver: Union[Role, SecurityContext],
        approved: bool,
        comment: str,
        in_memory_state: Optional[ExpenseAgentState] = None
    ) -> ExpenseAgentState:
        """异步版本人在回路恢复接口"""
        config = {"configurable": {"thread_id": thread_id}}
        if in_memory_state is not None:
            await self.graph.aupdate_state(config, in_memory_state.to_dict())

        payload = {
            "operator": approver,
            "approved": approved,
            "comment": comment
        }
        res = await self.graph.ainvoke(Command(resume=payload), config=config)
        state = self._convert_result_to_state(res)
        if hasattr(self.checkpointer, "delete_thread"):
            self.checkpointer.delete_thread(thread_id)
        return state

    def get_graph(self):
        """暴露 LangGraph 原生图对象，支持导出 Mermaid、可视化及内省"""
        return self.graph.get_graph()

    def stream(self, initial_state: ExpenseAgentState, **kwargs):
        """暴露 LangGraph 原生流式执行接口"""
        config = {"configurable": {"thread_id": initial_state.thread_id}}
        return self.graph.stream(initial_state, config=config, **kwargs)

    async def astream(self, initial_state: ExpenseAgentState, **kwargs):
        """暴露 LangGraph 原生异步流式执行接口"""
        config = {"configurable": {"thread_id": initial_state.thread_id}}
        async for chunk in self.graph.astream(initial_state, config=config, **kwargs):
            yield chunk
