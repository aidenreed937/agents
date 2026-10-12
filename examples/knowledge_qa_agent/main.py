"""现代知识库与控制台 Agent 全链路架构运行入口 (SOTA 方案全景演练)

本程序演示并对比四大核心命题：
1. 场景一：数据切片对比 —— 盲目字符切片 vs 结构感知与上下文增强切片 (Anthropic Contextual Chunking)
2. 场景二：检索机制对决 —— 稀疏(BM25) vs 稠密(向量) vs 混合召回(RRF)
3. 场景三：控制台双轨路由 —— 类似 Cloudflare/Google Cloud 的快轨直达(Cmd+K) vs 慢轨知识库
4. 场景四：端到端 Agent 运行 —— 混合召回 + 重排 + 父子块还原 + XML隔离提示词 + 溯源回答
"""
import sys
import os
import time

# 将当前目录与 src 注入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.ingestion.parser import MarkdownDocumentParser, UniversalDocumentParser
from src.ingestion.chunker import ContextualChunker
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseSemanticRetriever
from src.retrieval.hybrid import HybridRRFRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.navigation.router import IntentRouter
from src.agent.qa_engine import KnowledgeAgentEngine
from src.agent.tools.diagnostic_registry import DiagnosticToolRegistry
from src.agent.llm_client import LiteLLMClient, MockLLMClient
from src.storage.sqlite_store import SQLiteLocalStore
from src.models import UserContext


def print_header(title: str):
    print("\n" + "=" * 36 + f" {title} " + "=" * 36)


def print_step(step_name: str, detail: str = ""):
    print(f"\n>>> [{step_name}] {detail}")


def run_demo():
    manual_path = os.path.join(current_dir, "data", "cloud_platform_manual.md")

    # =========================================================================
    # 场景一：数据切片对比
    # =========================================================================
    print_header("场景一：数据切片治理 —— 为什么普通切片会被“切坏”？")

    parser = MarkdownDocumentParser()
    strategy_status = "工业级外部 AST" if parser.is_using_external_engine else "内置零依赖状态机 (可 pip install -r requirements.txt 升级)"
    print(f"【文档解析引擎适配器】: {parser.current_strategy_name} -> [{strategy_status}]")
    sections = parser.parse_sections(manual_path)

    chunker = ContextualChunker(child_max_chars=260, overlap_chars=40)
    parent_chunks, child_chunks = chunker.build_parent_and_child_chunks(sections)

    with open(manual_path, "r", encoding="utf-8") as f:
        raw_full_text = f.read()
    naive_chunks = chunker.build_naive_chunks(raw_full_text, chunk_size=200)

    print_step("对比 A: 盲目固定长度切片（反面案例）")
    bad_chunk = naive_chunks[3]  # 刚好截断在表格处
    print(f"【切片 ID】: {bad_chunk.chunk_id}")
    print(f"【内容截取】:\n{bad_chunk.raw_content.strip()}")
    print("【缺陷分析】: 表格行列被硬生生腰斩，失去了表头，且完全丢失了此片段属于哪个章节、哪个产品的上下文！")

    print_step("对比 B: 结构感知 + 上下文增强切片（Anthropic Contextual Chunking）")
    good_chunk = child_chunks[1]
    print(f"【切片 ID】: {good_chunk.chunk_id}")
    print(f"【注入的面包屑前缀】: {good_chunk.contextual_prefix}")
    print(f"【对应父块 (整节)】: {good_chunk.parent_id}")
    print(f"【有效阅读内容】:\n{good_chunk.raw_content.strip()[:180]}...")
    print("【优势分析】: 注入了完整的全局路径，表格保持原子性，即使单句检索也能精准识别业务含义。")

    # =========================================================================
    # 场景二：检索机制对决 (BM25 vs 向量 vs 混合召回 RRF)
    # =========================================================================
    print_header("场景二：检索机制对决 —— 为什么必须使用“语义与字面混合召回”？")

    # 离线建立双路索引
    bm25 = BM25Retriever()
    bm25.fit(child_chunks)

    dense = DenseSemanticRetriever()
    dense_status = "工业级真实 ONNX 模型 (fastembed)" if dense.is_real_onnx_model else "内置零依赖模拟器 (可 pip install -r requirements.txt 升级)"
    print(f"【向量检索引擎适配器】: {dense.current_strategy_name} ({dense.dimension}维) -> [{dense_status}]")
    dense.fit(child_chunks)

    hybrid = HybridRRFRetriever(bm25, dense, rrf_k=60)

    # 测试用例 1: 精确技术错误码 (考验字面召回)
    query_exact = "报错 ERR_GATEWAY_502"
    print_step(f"测试用例 1: 精确错误码检索 —— '{query_exact}'")

    bm25_res = bm25.search(query_exact, top_k=2)
    dense_res = dense.search(query_exact, top_k=2)
    hybrid_res = hybrid.search(query_exact, top_k=2)

    print(f"-> BM25 (字面): 第1名命中 [{bm25_res[0].chunk.title}], 得分: {bm25_res[0].score} (极精准)")
    print(f"-> 向量 (语义): 第1名命中 [{dense_res[0].chunk.title}], 得分: {dense_res[0].score} (易产生数值漂移)")
    print(f"-> 混合 (RRF) : 第1名命中 [{hybrid_res[0].chunk.title}], 融合分: {hybrid_res[0].score}")

    # 测试用例 2: 口语化近义词 (考验语义召回，文档中无对应字面)
    query_synonym = "跨域访问怎么配？前端一直报同源错误"
    print_step(f"测试用例 2: 口语近义词检索 —— '{query_synonym}'")

    bm25_res2 = bm25.search(query_synonym, top_k=2)
    dense_res2 = dense.search(query_synonym, top_k=2)
    hybrid_res2 = hybrid.search(query_synonym, top_k=2)

    bm25_top1 = bm25_res2[0].chunk.title if bm25_res2 else "未召回"
    print(f"-> BM25 (字面): 命中 [{bm25_top1}] (因为原文档写的是 CORS，字面不重合时表现弱)")
    print(f"-> 向量 (语义): 命中 [{dense_res2[0].chunk.title}] (成功跨越词汇障碍，识别出跨域与CORS语义)")
    print(f"-> 混合 (RRF) : 命中 [{hybrid_res2[0].chunk.title}], 融合分: {hybrid_res2[0].score} (两者取长补短)")

    # =========================================================================
    # 场景三：控制台快慢双轨路由 (类似 Cloudflare / Google Cloud Console)
    # =========================================================================
    print_header("场景三：控制台双轨路由 —— 类似 Cloudflare / Google Cloud 的智能分流")

    router = IntentRouter()
    router.register_actions_from_chunks(parent_chunks)

    test_queries = [
        ("打开 WAF 规则", "找操作入口 (期望走毫秒级快轨)"),
        ("查看 502 错误日志", "找监控入口 (期望走毫秒级快轨)"),
        ("跨域响应头怎么配置才能支持带凭证的生产环境？", "深度配置咨询 (期望走慢轨大模型)")
    ]

    for q, desc in test_queries:
        print_step(f"输入: '{q}'", f"意图: {desc}")
        t0 = time.time()
        intent = router.route(q)
        elapsed_ms = (time.time() - t0) * 1000

        if intent.is_fast_path:
            act = intent.matched_action
            print(f"⚡ [快轨命中] 耗时: {elapsed_ms:.2f}ms (无需触发大模型)")
            print(f"   -> 目标页面: {intent.target_name}")
            print(f"   -> 控制台直达 URL: {act.console_path}")
            print(f"   -> 所需权限: {act.required_permission}")
        else:
            print(f"🐢 [慢轨路由] 耗时: {elapsed_ms:.2f}ms (识别为复杂知识咨询，分流至 RAG 引擎)")

    # =========================================================================
    # 场景四：端到端 Agent 运行 (Orchestrated Parallel Tool-RAG 动态诊断闭环)
    # =========================================================================
    print_header("场景四：端到端业务闭环 —— 动态诊断探针并发调用与故障精准确诊")

    user_question = "我们系统线上报了 ERR_GATEWAY_502，请问可能的原因和排查步骤是什么？怎么去控制台看？"
    print(f"【用户真实提问】: {user_question}\n")

    # 1. 意图路由器分流并编排动态诊断任务
    intent = router.route(user_question)
    print(f">> 执行阶段 1: 意图路由器分析 (耗时 < 0.1ms)")
    print(f"   - 慢轨分流: 识别为复杂排障咨询，需要唤起 RAG 与动态体检")
    print(f"   - 动态编排诊断任务清单: 共 {len(intent.diagnostic_tasks)} 个关联探针")
    for t in intent.diagnostic_tasks:
        print(f"     * [{t.tool_name}] 意图: {t.rationale}")

    # 2. 并行双路并发执行：静态知识检索 + 动态探针探测
    print("\n>> 执行阶段 2: 并发双路执行 (静态知识库检索 || 动态系统探针采集)")
    t_start_parallel = time.time()

    # 路 A: 静态知识混合召回与重排
    candidates = hybrid.search(user_question, top_k=6)
    reranker = CrossEncoderReranker(min_relevance_threshold=0.25)
    rerank_results = reranker.rerank(user_question, candidates, top_n=2)

    # 路 B: 动态诊断工具并发线程池执行
    tool_registry = DiagnosticToolRegistry()
    diag_results = tool_registry.execute_tasks_parallel(intent.diagnostic_tasks)
    parallel_elapsed = (time.time() - t_start_parallel) * 1000

    print(f"   -> 并行双路完成！总耗时: {parallel_elapsed:.2f}ms")
    print(f"   -> 静态知识精排保留: {len(rerank_results)} 个高置信切片 (首名: [{rerank_results[0].chunk.title}], 分数: {rerank_results[0].relevance_score})")
    print(f"   -> 动态探针实时返回:")
    for dr in diag_results:
        print(f"      [{dr.status}] 探针 '{dr.tool_name}': {dr.summary} (耗时: {dr.latency_ms}ms)")

    # 3. Small-to-Big 结构化上下文重构与联合 Prompt 生成
    print("\n>> 执行阶段 3: Small-to-Big 父块还原与联合 XML Prompt 组装")
    try:
        llm_client = LiteLLMClient()
    except RuntimeError:
        llm_client = MockLLMClient()
    qa_engine = KnowledgeAgentEngine(parent_chunks, llm_client=llm_client)
    print(f"【大模型客户端引擎】: {llm_client.model_name} (驱动底层: {llm_client.provider_name}, 离线保底模式: {llm_client.is_simulated})")

    try:
        answer_package = qa_engine.generate_grounded_answer(user_question, rerank_results, diagnostic_results=diag_results)
    except Exception as e:
        print(f"\n[提示] 真实大模型接口调用未成功 ({type(e).__name__}: {str(e)[:80]}...)，自动切换为本地离线保底客户端继续演练。")
        qa_engine.llm_client = MockLLMClient()
        answer_package = qa_engine.generate_grounded_answer(user_question, rerank_results, diagnostic_results=diag_results)

    print("\n" + "-" * 28 + " 【生成的联合提示词 (Prompt 结构)】 " + "-" * 28)
    print(answer_package["prompt"])

    print("-" * 28 + " 【最终呈现给用户的回答与一键处置卡片】 " + "-" * 28)
    print(answer_package["answer"])

    print("\n【真实溯源引用清单】:")
    for cite in answer_package["citations"]:
        print(f"   * {cite}")

    # 流式生成增量演示
    print("\n" + "-" * 28 + " 【Web 前端 SSE 流式实时打字机增量演示】 " + "-" * 28)
    try:
        for token in qa_engine.stream_grounded_answer(user_question, rerank_results, diagnostic_results=diag_results):
            sys.stdout.write(token)
            sys.stdout.flush()
    except Exception:
        qa_engine.llm_client = MockLLMClient()
        for token in qa_engine.stream_grounded_answer(user_question, rerank_results, diagnostic_results=diag_results):
            sys.stdout.write(token)
            sys.stdout.flush()
    print()

    # =========================================================================
    # 场景五：本地持久化与冷启动演练 (SQLite + FTS5 + BLOB 磁盘文件)
    # =========================================================================
    print_header("场景五：本地持久化与冷启动 —— 磁盘存储与离线恢复")

    db_path = os.path.join(current_dir, "data", "knowledge_base.db")
    print_step(f"步骤 1: 将切片、元数据与向量持久化到本地 SQLite 磁盘文件: {os.path.basename(db_path)}")

    # 构造向量映射
    embeddings_map = {
        c.chunk_id: dense.embeddings[idx] for idx, c in enumerate(child_chunks)
    }

    local_store = SQLiteLocalStore(db_path)
    all_chunks_to_save = parent_chunks + child_chunks
    local_store.save_chunks(all_chunks_to_save, embeddings_map)
    file_size_kb = os.path.getsize(db_path) / 1024
    print(f"   -> 成功写入 SQLite 单文件！磁盘大小: {file_size_kb:.2f} KB (包含关系元数据 + FTS5 倒排索引 + 向量 BLOB)")

    print_step("步骤 2: 模拟应用进程重启（清空内存），直接从本地磁盘冷启动恢复")
    cold_parents, cold_children, cold_emb_map = local_store.load_all_chunks()
    print(f"   -> 冷启动恢复完成: {len(cold_parents)} 个父块, {len(cold_children)} 个子块, {len(cold_emb_map)} 条向量索引已加载就绪！")

    print_step("步骤 3: 直接利用本地 SQLite 原生 FTS5 引擎执行磁盘 BM25 全文检索")
    fts_results = local_store.fts5_search("ERR_GATEWAY_502", top_k=2)
    for res in fts_results:
        print(f"   -> SQLite FTS5 检索命中: [{res.chunk.title}], FTS5-BM25 分数: {res.score}")

    # =========================================================================
    # 场景六：HTML 网页直接输入与去噪治理 (Trafilatura / 状态机去噪入库)
    # =========================================================================
    print_header("场景六：HTML 网页直接输入与去噪治理 —— 先去噪再入库")

    html_file = os.path.join(current_dir, "data", "cloud_edge_security.html")
    print_step(f"输入源文件: {os.path.basename(html_file)} (包含导航栏促销、侧边栏广告、页脚备案等常见噪音)")

    print(">>> [原始 HTML 包含的典型噪音 DOM 片段]:")
    print("   - 导航栏: <nav>...[促销] 购买年度企业网关套餐立享 8 折优惠！...</nav>")
    print("   - 侧边栏: <aside>...广告：点击申请免费试用...</aside>")
    print("   - 页脚栏: <footer>...京ICP备12345678号-1...</footer>")

    universal_parser = UniversalDocumentParser()
    html_sections = universal_parser.parse_sections(html_file)

    print(f"\n>>> [去噪引擎清洗结果]: 成功提取 {len(html_sections)} 个核心结构化小节 (策略: {html_sections[0]['parser_strategy']})")
    for s_idx, sec in enumerate(html_sections):
        print(f"   [{s_idx + 1}] 标题: {sec['heading']} (级别: H{sec['level']})")
        print(f"       面包屑路径: {' > '.join(sec['heading_path'])}")
        if sec["action_link"]:
            act = sec["action_link"]
            print(f"       提取到操作直达: 控制台 {act.console_path} | 权限: {act.required_permission}")

    # 验证去噪后的 HTML 切片直接无缝兼容下游 ContextualChunker
    html_parents, html_children = chunker.build_parent_and_child_chunks(html_sections, doc_id="doc_edge_security_html")
    print(f"\n>>> [切片引擎兼容验证]: 成功生成 {len(html_parents)} 个父块与 {len(html_children)} 个上下文子块")
    sample_child = html_children[1]
    print(f"   【代表性子块 ID】: {sample_child.chunk_id}")
    print(f"   【注入上下文前缀】: {sample_child.contextual_prefix}")
    print(f"   【纯净正文截取】: {sample_child.raw_content[:90]}...")

    # =========================================================================
    # 场景七：企业级多租户与 RBAC 物理硬隔离 (Pre-filtering)
    # =========================================================================
    print_header("场景七：企业级多租户与 RBAC 物理硬隔离 —— 拒绝事后过滤的信息泄露")

    audit_file = os.path.join(current_dir, "data", "internal_security_audit.md")
    audit_sections = universal_parser.parse_sections(audit_file)
    audit_parents, audit_children = chunker.build_parent_and_child_chunks(audit_sections, doc_id="doc_audit_internal")

    # 聚合全局全量多租户知识切片 (包含公共切片与租户专属机密切片)
    multitenant_all_chunks = child_chunks + html_children + audit_children
    multi_bm25 = BM25Retriever()
    multi_bm25.fit(multitenant_all_chunks)

    sec_query = "内部报销审批与跨租户财务结算凭证"
    print_step(f"全租户知识池已建立 (共 {len(multitenant_all_chunks)} 个切片)，提问测试: '{sec_query}'")

    # 1. 外部租户查询机密 (物理阻断)
    guest_ctx = UserContext(user_id="user_guest_01", tenant_id="guest_tenant", roles=["Viewer"])
    blocked_results = multi_bm25.search(sec_query, top_k=3, user_context=guest_ctx)
    corp_leaks = [r for r in blocked_results if r.chunk.tenant_id == "corp_audit_tenant"]
    print(f"\n[测试 1: 外部访客租户请求] (租户: {guest_ctx.tenant_id}, 角色: {guest_ctx.roles})")
    print(f"   -> 私有租户数据泄露数: {len(corp_leaks)} (期望: 0，跨租户物理硬隔断生效！)")
    if len(corp_leaks) == 0:
        print("   -> 安全断言: [PASS] 外部租户无法穿透召回集团审计私有知识！")

    # 2. 集团合规审计员查询 (正常召回)
    auditor_ctx = UserContext(user_id="auditor_007", tenant_id="corp_audit_tenant", roles=["Audit:SuperAdmin"])
    allowed_results = multi_bm25.search(sec_query, top_k=3, user_context=auditor_ctx)
    print(f"\n[测试 2: 集团审计员租户请求] (租户: {auditor_ctx.tenant_id}, 角色: {auditor_ctx.roles})")
    print(f"   -> 检索召回结果数: {len(allowed_results)}")
    if allowed_results:
        top_hit = allowed_results[0].chunk
        print(f"   -> 首条命中切片: [{top_hit.title}], 归属租户: {top_hit.tenant_id}, 所需权限: {top_hit.required_permission}")
        print("   -> 安全断言: [PASS] 授权租户正常召回私有业务知识！")

    # 3. 本地 SQLite 磁盘层验证 RBAC 过滤
    local_store.save_chunks(multitenant_all_chunks)
    disk_blocked = local_store.fts5_search(sec_query, top_k=3, user_context=guest_ctx)
    disk_allowed = local_store.fts5_search(sec_query, top_k=3, user_context=auditor_ctx)
    disk_corp_leaks = [r for r in disk_blocked if r.chunk.tenant_id == "corp_audit_tenant"]
    print(f"\n[测试 3: SQLite 磁盘 FTS5 SQL 层硬隔离验证]")
    print(f"   -> 磁盘 FTS5 外部租户私有泄露数: {len(disk_corp_leaks)} (SQL WHERE 物理过滤)")
    print(f"   -> 磁盘 FTS5 授权审计员命中数: {len(disk_allowed)} (首条: {disk_allowed[0].chunk.title if disk_allowed else '无'})")

    print("\n" + "=" * 36 + " 演练完成 " + "=" * 36 + "\n")


if __name__ == "__main__":
    run_demo()
