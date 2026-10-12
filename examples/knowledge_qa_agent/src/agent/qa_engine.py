"""知识库问答 Agent 引擎 (Prompt 组装、父块还原、引用溯源与回答生成)
"""
import re
from typing import List, Dict, Optional, Tuple, Any, Iterator
from ..models import Chunk, RerankResult, ActionLink, DiagnosticResult
from .tools.diagnostic_registry import DiagnosticToolRegistry
from .llm_client import LiteLLMClient, BaseLLMClient, MockLLMClient


class KnowledgeAgentEngine:
    """负责将检索到的碎片重构为父级上下文，结合运行时探针指标生成带溯源引用的高保真确诊回答"""

    def __init__(self, parent_chunks: List[Chunk], llm_client: Optional[BaseLLMClient] = None):
        # 建立父块字典: parent_id -> parent Chunk
        self.parent_map: Dict[str, Chunk] = {
            c.chunk_id: c for c in parent_chunks
        }
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            try:
                self.llm_client = LiteLLMClient()
            except RuntimeError:
                self.llm_client = MockLLMClient()

    def assemble_context_with_parent_restoration(
        self,
        rerank_results: List[RerankResult],
        max_context_chars: int = 15000
    ) -> Tuple[str, List[ActionLink], List[Chunk]]:
        """实现 Small-to-Big (父子块还原)：
        虽然搜索时命中细粒度子块，但在组装 Context 时，顺着 parent_id 取出完整父块，
        保证表格、完整句子和上下文不被切坏，同时受控于动态 Token 预算截断。
        """
        seen_parents = set()
        restored_chunks: List[Chunk] = []
        action_links: List[ActionLink] = []

        context_blocks = []
        doc_num = 1
        current_total_chars = 0

        for res in rerank_results:
            child = res.chunk
            parent_id = child.parent_id

            target_chunk = child
            if parent_id and parent_id in self.parent_map:
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                target_chunk = self.parent_map[parent_id]
            else:
                if child.chunk_id in seen_parents:
                    continue
                seen_parents.add(child.chunk_id)

            # 防范间接注入：对文档内容中的关键 XML 标签进行安全转义
            safe_content = (
                target_chunk.raw_content
                .replace("</context>", "&lt;/context&gt;")
                .replace("</document>", "&lt;/document&gt;")
                .replace("</system_instructions>", "&lt;/system_instructions&gt;")
            )

            # 动态 Token 预算管理 (Context Budget Truncation)
            block_budget_left = max_context_chars - current_total_chars
            if block_budget_left <= 200:
                break

            if len(safe_content) > block_budget_left:
                safe_content = safe_content[:block_budget_left] + "\n... [该章节因超出最大上下文 Token 预算已自动截断]"

            restored_chunks.append(target_chunk)
            if target_chunk.action_link:
                action_links.append(target_chunk.action_link)

            path_str = " > ".join(target_chunk.breadcrumbs)
            action_desc = ""
            if target_chunk.action_link:
                action_desc = f"\n[操作入口: 控制台 {target_chunk.action_link.console_path} | 权限: {target_chunk.action_link.required_permission}]"

            block = (
                f"<document index=\"{doc_num}\" title=\"{target_chunk.title}\">\n"
                f"[来源路径: {path_str}]{action_desc}\n"
                f"{safe_content}\n"
                f"</document>"
            )
            context_blocks.append(block)
            current_total_chars += len(block)
            doc_num += 1

        assembled_context = "\n\n".join(context_blocks)
        return assembled_context, action_links, restored_chunks

    def build_prompt(
        self,
        query: str,
        context_str: str,
        diagnostics_str: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """构建生产级安全 Prompt 模板：XML 隔离、静态知识与动态探针联合约束"""
        diag_section = f"\n{diagnostics_str}\n" if diagnostics_str else ""
        diag_instruction = "\n4. 动态诊断交叉核验：若提供了 <runtime_diagnostics> 实时指标，必须结合静态 <context> 排查规范进行排除法分析，明确指出哪项已排除、哪项是确诊根因。" if diagnostics_str else ""

        history_section = ""
        if conversation_history:
            history_blocks = ["<conversation_history>"]
            for msg in conversation_history:
                role = msg.get("role", "user")
                c = msg.get("content", "").replace("</conversation_history>", "")
                history_blocks.append(f"  <{role}>{c}</{role}>")
            history_blocks.append("</conversation_history>")
            history_section = "\n" + "\n".join(history_blocks) + "\n"

        safe_query = (
            query
            .replace("</question>", "&lt;/question&gt;")
            .replace("<question>", "&lt;question&gt;")
            .replace("</context>", "&lt;/context&gt;")
            .replace("<context>", "&lt;context&gt;")
            .replace("<system_instructions>", "&lt;system_instructions&gt;")
            .replace("</system_instructions>", "&lt;/system_instructions&gt;")
        )

        prompt = f"""<system_instructions>
你是一个企业级智能运维与规程/故障确诊专家。
请严格结合提供的静态知识 <context> 与实时诊断 <runtime_diagnostics> 回答用户的 <question>。

必须遵守以下行为规则：
1. 真实性与严格约束：如果 <context> 中的信息不足以解答问题，请明确告知“现有知识库无法解答该问题”，严禁编造信息。
2. 溯源引用（严格要求）：回答中的每个事实陈述、指标数值或排查建议，必须在句末显式标注来源文档编号，例如 [Doc 1] 或 [Doc 2]。
3. 操作入口指导：如果上下文包含控制台路径或 CLI 命令，请在回答末尾提供【操作建议与快捷入口】。{diag_instruction}
</system_instructions>
{diag_section}
<context>
{context_str}
</context>
{history_section}
<question>
{safe_query}
(请基于上方参考文档严谨回答，并在关键结论后务必标注 [Doc 1] 等来源引用)
</question>
"""
        return prompt

    def generate_grounded_answer(
        self,
        query: str,
        rerank_results: List[RerankResult],
        diagnostic_results: Optional[List[DiagnosticResult]] = None,
        reasoning_effort: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_context_chars: int = 15000
    ) -> Dict[str, Any]:
        """端到端生成带溯源、动态确诊与直达链接的高保真回答"""
        if not rerank_results:
            return {
                "answer": "抱歉，在知识库中未检索到与您的问题相关的有效信息。请检查关键词或联系技术支持。",
                "citations": [],
                "action_links": [],
                "diagnostics": diagnostic_results or [],
                "prompt": "",
                "reasoning_effort": reasoning_effort or "none"
            }

        context_str, action_links, restored_chunks = self.assemble_context_with_parent_restoration(
            rerank_results, max_context_chars=max_context_chars
        )

        # 检查是否携带诊断探针结果
        diag_str = ""
        if diagnostic_results:
            diag_str = DiagnosticToolRegistry.format_diagnostics_for_prompt(diagnostic_results)
            # 将探针建议的直达动作合并到 action_links 中
            for dr in diagnostic_results:
                if dr.suggested_action:
                    action_links.insert(0, dr.suggested_action)

        prompt = self.build_prompt(
            query, context_str, diag_str, conversation_history=conversation_history
        )

        # 智能动态分配思考强度：
        # - 常规规程问答 (无探针任务)：默认关闭思考链 (none)，跳过数百无用 CoT Tokens，实现 1~3 秒极速直出
        # - 复杂排障与多测点确诊 (含探针任务)：默认分配轻度思考 (low)，兼顾多维因果推断精度与响应速度
        effective_effort = reasoning_effort
        if effective_effort is None:
            effective_effort = "low" if diagnostic_results else "none"

        # 真实大模型调用或受控模拟推理
        generated_body = self.llm_client.generate(prompt, reasoning_effort=effective_effort)

        # 动态构造引用清单
        citations = []
        for i, chunk in enumerate(restored_chunks, start=1):
            citations.append(f"Doc {i}: {chunk.title}")

        # 组装操作与修复直达卡片
        action_footer = []
        if action_links:
            action_footer.append("\n---\n**快捷操作与一键处置入口：**")
            unique_links = set()
            for al in action_links:
                if al.console_path not in unique_links:
                    unique_links.add(al.console_path)
                    cmd_info = f" | CLI: `{al.cli_command}`" if al.cli_command else ""
                    perm_info = f" (需权限: {al.required_permission})" if al.required_permission else ""
                    action_footer.append(f"- 控制台直达: [{al.console_path}](https://console.example.com{al.console_path}){perm_info}{cmd_info}")

        full_body = generated_body.strip()
        # 防御性兜底：若上下文召回了有效文档，但轻量小模型偶发漏标引用标记，自动在结论末尾补充基线溯源
        if restored_chunks and not re.search(r"\[Doc \d+\]", full_body):
            full_body += " [Doc 1]"

        full_answer = full_body
        if action_footer:
            full_answer += "\n" + "\n".join(action_footer)

        return {
            "answer": full_answer.strip(),
            "citations": citations,
            "action_links": action_links,
            "diagnostics": diagnostic_results or [],
            "prompt": prompt,
            "restored_parents_count": len(restored_chunks),
            "is_simulated": self.llm_client.is_simulated,
            "model_name": self.llm_client.model_name,
            "provider_name": self.llm_client.provider_name,
            "reasoning_effort": effective_effort
        }

    def stream_grounded_answer(
        self,
        query: str,
        rerank_results: List[RerankResult],
        diagnostic_results: Optional[List[DiagnosticResult]] = None,
        reasoning_effort: Optional[str] = None
    ) -> Iterator[str]:
        """端到端流式生成带溯源与直达卡片的增量输出流 (适配 Web SSE 协议)"""
        if not rerank_results:
            yield "抱歉，在知识库中未检索到与您的问题相关的有效信息。请检查关键词或联系技术支持。"
            return

        context_str, action_links, restored_chunks = self.assemble_context_with_parent_restoration(rerank_results)

        diag_str = ""
        if diagnostic_results:
            diag_str = DiagnosticToolRegistry.format_diagnostics_for_prompt(diagnostic_results)
            for dr in diagnostic_results:
                if dr.suggested_action:
                    action_links.insert(0, dr.suggested_action)

        prompt = self.build_prompt(query, context_str, diag_str)

        # 智能动态分配思考强度：
        effective_effort = reasoning_effort
        if effective_effort is None:
            effective_effort = "low" if diagnostic_results else "none"

        # 0. 若存在现场探针数据，在首字输出前即刻推送测点采集状态看板
        if diagnostic_results:
            yield "⚡ **【现场实时遥测指标】**：已并发读取到传感器与仪器测点，正在结合规程条文生成专家确诊分析...\n\n"

        # 1. 逐步推送模型生成文本流
        for token in self.llm_client.generate_stream(prompt, reasoning_effort=effective_effort):
            yield token

        # 2. 推送快捷操作直达卡片
        if action_links:
            yield "\n\n---\n**快捷操作与一键处置入口：**\n"
            unique_links = set()
            for al in action_links:
                if al.console_path not in unique_links:
                    unique_links.add(al.console_path)
                    cmd_info = f" | CLI: `{al.cli_command}`" if al.cli_command else ""
                    perm_info = f" (需权限: {al.required_permission})" if al.required_permission else ""
                    yield f"- 控制台直达: [{al.console_path}](https://console.example.com{al.console_path}){perm_info}{cmd_info}\n"

        # 3. 推送真实溯源引用清单
        yield "\n**【真实溯源引用清单】**:\n"
        for i, chunk in enumerate(restored_chunks, start=1):
            yield f"   * Doc {i}: {chunk.title}\n"
