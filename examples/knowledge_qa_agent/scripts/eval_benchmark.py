"""自动化质量评测基准套件与版本追溯引擎 (Offline RAG & Navigation Benchmark)

架构解耦设计：
1. 【数据层分离 (Data Layer)】: 测试用例独立存储于 eval_data/*.json(l)，内置 DatasetLoader 支持模型自动生成的非标异构数据
2. 【配置层分离 (Config Layer)】: 检索超参、目录路径与质量门禁基线独立存储于 eval_config.json
3. 【逻辑层解耦 (Logic Layer)】: 核心评测计算、快照持久化、Diff 对比引擎、CI 质量门禁高度纯粹化
"""
import os
import sys
import time
import json
import glob
import datetime
import statistics
import unittest
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field

# 注入当前目录与项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
for p in [project_root, current_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.ingestion.parser import UniversalDocumentParser
from src.ingestion.chunker import ContextualChunker
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseSemanticRetriever
from src.retrieval.hybrid import HybridRRFRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.navigation.router import IntentRouter
from src.agent.qa_engine import KnowledgeAgentEngine
from src.agent.tools.diagnostic_registry import DiagnosticToolRegistry
from src.models import Chunk, ActionLink, DiagnosticResult, UserContext


# =============================================================================
# 一、 配置层 (Config Layer)
# =============================================================================
@dataclass
class EvalConfig:
    """评测系统配置契约，支持从 JSON 文件加载与代码默认兜底"""
    # 路径配置
    default_dataset: str = "eval_data/golden_dataset.json"
    data_dir: str = "data"
    history_dir: str = "eval_history"
    default_report: str = "reports/benchmark_report.md"

    # 检索超参
    top_k_candidates: int = 6
    top_n_rerank: int = 3
    rrf_k: int = 60
    min_relevance_threshold: float = 0.22
    chunk_child_chars: int = 260
    chunk_overlap_chars: int = 40

    # 质量门禁基线阈值
    routing_overall_acc_min: float = 0.90
    routing_fast_f1_min: float = 0.90
    routing_path_match_min: float = 0.95
    hit_rate_at_1_min: float = 0.75
    hit_rate_at_3_min: float = 0.85
    mrr_min: float = 0.80
    rerank_retention_min: float = 0.90
    grounded_citation_min: float = 0.95
    out_of_domain_refusal_min: float = 1.00

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "EvalConfig":
        """加载配置文件，若文件不存在则使用工业标准默认值"""
        target = config_path or os.path.join(project_root, "eval_config.json")
        if not os.path.exists(target):
            return cls()

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)

            paths = data.get("paths", {})
            ret = data.get("retrieval", {})
            gates = data.get("gate_thresholds", {})

            return cls(
                default_dataset=paths.get("default_dataset", "eval_data/golden_dataset.json"),
                data_dir=paths.get("data_dir", "data"),
                history_dir=paths.get("history_dir", "eval_history"),
                default_report=paths.get("default_report", "reports/benchmark_report.md"),
                top_k_candidates=ret.get("top_k_candidates", 6),
                top_n_rerank=ret.get("top_n_rerank", 3),
                rrf_k=ret.get("rrf_k", 60),
                min_relevance_threshold=ret.get("min_relevance_threshold", 0.22),
                chunk_child_chars=ret.get("chunk_child_chars", 260),
                chunk_overlap_chars=ret.get("chunk_overlap_chars", 40),
                routing_overall_acc_min=gates.get("routing_overall_acc_min", 0.90),
                routing_fast_f1_min=gates.get("routing_fast_f1_min", 0.90),
                routing_path_match_min=gates.get("routing_path_match_min", 0.95),
                hit_rate_at_1_min=gates.get("hit_rate_at_1_min", 0.75),
                hit_rate_at_3_min=gates.get("hit_rate_at_3_min", 0.85),
                mrr_min=gates.get("mrr_min", 0.80),
                rerank_retention_min=gates.get("rerank_retention_min", 0.90),
                grounded_citation_min=gates.get("grounded_citation_min", 0.95),
                out_of_domain_refusal_min=gates.get("out_of_domain_refusal_min", 1.00),
            )
        except Exception:
            return cls()


# =============================================================================
# 二、 数据层 (Data Layer & Synthetic Adapter)
# =============================================================================
@dataclass
class BenchmarkItem:
    """评测基准样本数据契约"""
    item_id: str
    query: str
    category: str                                 # "fast_track" | "rag_qa" | "rbac_action" | "out_of_domain"
    expected_fast_path: bool                      # 期望是否走快轨直达
    expected_console_path: Optional[str] = None   # 快轨或动作卡片期望路径
    expected_permission: Optional[str] = None     # 期望关联的 RBAC 权限
    target_keywords: List[str] = field(default_factory=list) # 评估检索命中率的关键术语 (切片标题、路径、正文或元数据需包含)
    should_refuse: bool = False                   # 负向越界样本是否期望拒答/未检索到
    user_context: Optional[UserContext] = None    # 模拟发起提问的用户上下文 (RBAC 角色与租户隔离)


class DatasetLoader:
    """数据集加载与适配器：
    支持标准 JSON List、大模型流式生成的 JSONL、以及非标异构字段别名归一化。
    即使测试用例是由不同 LLM 自动化批量生成的，也能实现平滑解析。
    """

    # 常见模型生成数据时的字段别名映射表
    QUERY_ALIASES = ["query", "question", "prompt", "input", "user_query", "text"]
    CATEGORY_ALIASES = ["category", "type", "intent", "scene", "task"]
    FAST_PATH_ALIASES = ["expected_fast_path", "is_fast", "is_fast_path", "fast_track", "direct_nav", "fast_path"]
    CONSOLE_PATH_ALIASES = ["expected_console_path", "console_path", "target_path", "action_path", "expected_path"]
    PERMISSION_ALIASES = ["expected_permission", "permission", "required_permission", "role"]
    KEYWORDS_ALIASES = ["target_keywords", "ground_truth_keywords", "keywords", "expected_chunks", "ground_truth", "answers"]
    REFUSE_ALIASES = ["should_refuse", "is_negative", "out_of_domain", "refuse", "negative"]
    USER_CTX_ALIASES = ["user_context", "user", "context", "auth", "caller"]

    @classmethod
    def _extract_field(cls, raw: Dict[str, Any], aliases: List[str], default: Any = None) -> Any:
        for a in aliases:
            if a in raw and raw[a] is not None:
                return raw[a]
        return default

    @classmethod
    def _normalize_item(cls, raw: Dict[str, Any], index: int) -> Optional[BenchmarkItem]:
        """将任意异构字典归一化为标准的 BenchmarkItem"""
        query_val = cls._extract_field(raw, cls.QUERY_ALIASES)
        if not query_val or not isinstance(query_val, str) or not query_val.strip():
            return None

        query = query_val.strip()
        item_id = str(raw.get("item_id") or raw.get("id") or f"case_{index:03d}")

        # 类别识别
        cat_val = cls._extract_field(raw, cls.CATEGORY_ALIASES, "rag_qa")
        cat_clean = str(cat_val).lower().strip()
        category = "rag_qa"
        if any(w in cat_clean for w in ["fast", "nav", "route", "jump"]):
            category = "fast_track"
        elif any(w in cat_clean for w in ["rbac", "perm", "auth", "action"]):
            category = "rbac_action"
        elif any(w in cat_clean for w in ["negative", "out", "refuse", "domain"]):
            category = "out_of_domain"

        # 快轨标记转换
        fast_raw = cls._extract_field(raw, cls.FAST_PATH_ALIASES)
        if fast_raw is not None:
            if isinstance(fast_raw, bool):
                expected_fast = fast_raw
            else:
                expected_fast = str(fast_raw).lower() in ["true", "1", "yes", "fast"]
        else:
            expected_fast = (category == "fast_track")

        # 路径与权限
        expected_path = cls._extract_field(raw, cls.CONSOLE_PATH_ALIASES)
        expected_perm = cls._extract_field(raw, cls.PERMISSION_ALIASES)

        # 关键词提取
        kw_raw = cls._extract_field(raw, cls.KEYWORDS_ALIASES, [])
        target_keywords: List[str] = []
        if isinstance(kw_raw, list):
            target_keywords = [str(k).strip() for k in kw_raw if str(k).strip()]
        elif isinstance(kw_raw, str) and kw_raw.strip():
            target_keywords = [kw_raw.strip()]

        # 拒答标记
        refuse_raw = cls._extract_field(raw, cls.REFUSE_ALIASES)
        if refuse_raw is not None:
            if isinstance(refuse_raw, bool):
                should_refuse = refuse_raw
            else:
                should_refuse = str(refuse_raw).lower() in ["true", "1", "yes", "refuse"]
        else:
            should_refuse = (category == "out_of_domain")

        # 解析用户上下文 (RBAC 与租户隔离)
        user_ctx_raw = cls._extract_field(raw, cls.USER_CTX_ALIASES)
        user_context = None
        if isinstance(user_ctx_raw, dict):
            user_context = UserContext(
                user_id=user_ctx_raw.get("user_id", "test_user"),
                tenant_id=user_ctx_raw.get("tenant_id", "public"),
                roles=user_ctx_raw.get("roles", ["Viewer"]) if isinstance(user_ctx_raw.get("roles"), list) else [str(user_ctx_raw.get("roles"))],
                permissions=user_ctx_raw.get("permissions", []) if isinstance(user_ctx_raw.get("permissions"), list) else []
            )
        elif "tenant_id" in raw or "roles" in raw:
            user_context = UserContext(
                user_id=raw.get("user_id", "test_user"),
                tenant_id=raw.get("tenant_id", "public"),
                roles=raw.get("roles", ["Viewer"]) if isinstance(raw.get("roles"), list) else [str(raw.get("roles"))],
                permissions=raw.get("permissions", []) if isinstance(raw.get("permissions"), list) else []
            )

        return BenchmarkItem(
            item_id=item_id,
            query=query,
            category=category,
            expected_fast_path=expected_fast,
            expected_console_path=expected_path,
            expected_permission=expected_perm,
            target_keywords=target_keywords,
            should_refuse=should_refuse,
            user_context=user_context
        )

    @classmethod
    def load_dataset(cls, dataset_path: str) -> List[BenchmarkItem]:
        """智能解析外部评测集文件（兼容 .json 和 .jsonl 格式）"""
        if not os.path.isabs(dataset_path):
            dataset_path = os.path.join(project_root, dataset_path)

        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"评测集文件不存在: {dataset_path}")

        items: List[BenchmarkItem] = []

        # 1. 尝试以 JSONL (按行解析)
        is_jsonl = dataset_path.endswith(".jsonl")
        if is_jsonl:
            with open(dataset_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        raw_dict = json.loads(line)
                        norm = cls._normalize_item(raw_dict, line_idx)
                        if norm:
                            items.append(norm)
                    except json.JSONDecodeError:
                        continue
            return items

        # 2. 尝试以标准 JSON 解析 (List 或外层包裹字典)
        with open(dataset_path, "r", encoding="utf-8") as f:
            content = json.load(f)

        raw_list = []
        if isinstance(content, list):
            raw_list = content
        elif isinstance(content, dict):
            # 支持模型生成时外层套 {"cases": [...]} 或 {"data": [...]}
            for key in ["cases", "samples", "data", "benchmark", "items"]:
                if key in content and isinstance(content[key], list):
                    raw_list = content[key]
                    break
            if not raw_list:
                raw_list = [content]

        for idx, entry in enumerate(raw_list, 1):
            if isinstance(entry, dict):
                norm = cls._normalize_item(entry, idx)
                if norm:
                    items.append(norm)

        return items


# =============================================================================
# 三、 逻辑层 (Logic Layer)
# =============================================================================
def get_git_info() -> Tuple[str, str]:
    """通过纯标准库安全读取 .git 状态，提取当前分支和 Commit Hash"""
    branch = "unknown"
    commit = "unknown"
    try:
        git_dir = os.path.join(current_dir, "..", "..", ".git")
        if not os.path.exists(git_dir):
            git_dir = os.path.join(current_dir, ".git")

        head_path = os.path.join(git_dir, "HEAD")
        if os.path.exists(head_path):
            with open(head_path, "r", encoding="utf-8") as f:
                head_content = f.read().strip()
            if head_content.startswith("ref:"):
                ref_subpath = head_content.split(":", 1)[1].strip()
                branch = os.path.basename(ref_subpath)
                ref_full = os.path.join(git_dir, ref_subpath)
                if os.path.exists(ref_full):
                    with open(ref_full, "r", encoding="utf-8") as rf:
                        commit = rf.read().strip()[:8]
            else:
                commit = head_content[:8]
                branch = "detached"
    except Exception:
        pass
    return branch, commit


class BenchmarkEvaluator:
    """自动化评测运行执行器（与数据和配置解耦）"""

    def __init__(self, config: EvalConfig):
        self.config = config
        self.data_dir = os.path.join(project_root, config.data_dir)
        self.parser = UniversalDocumentParser()
        self.chunker = ContextualChunker(
            child_max_chars=config.chunk_child_chars,
            overlap_chars=config.chunk_overlap_chars
        )
        self.parent_chunks: List[Chunk] = []
        self.child_chunks: List[Chunk] = []

        self._build_index()

    def _build_index(self):
        """解析数据目录下多源文档（Markdown 手册、HTML 网页、多租户私有文档），完成切片并建立检索索引"""
        files = sorted(
            [f for f in glob.glob(os.path.join(self.data_dir, "*")) if f.endswith((".md", ".html"))]
        )

        all_parents: List[Chunk] = []
        all_children: List[Chunk] = []

        for fpath in files:
            if not os.path.exists(fpath):
                continue
            sections = self.parser.parse_sections(fpath)
            doc_id = os.path.splitext(os.path.basename(fpath))[0]
            p_chunks, c_chunks = self.chunker.build_parent_and_child_chunks(sections, doc_id=doc_id)
            all_parents.extend(p_chunks)
            all_children.extend(c_chunks)

        self.parent_chunks = all_parents
        self.child_chunks = all_children

        # 1. 路由器初始化
        self.router = IntentRouter()
        self.router.register_actions_from_chunks(self.parent_chunks)

        # 2. 混合检索引擎
        self.bm25 = BM25Retriever()
        self.bm25.fit(self.child_chunks)

        self.dense = DenseSemanticRetriever()
        self.dense.fit(self.child_chunks)

        self.hybrid = HybridRRFRetriever(self.bm25, self.dense, rrf_k=self.config.rrf_k)
        self.reranker = CrossEncoderReranker(min_relevance_threshold=self.config.min_relevance_threshold)
        self.diagnostic_registry = DiagnosticToolRegistry()
        self.qa_engine = KnowledgeAgentEngine(self.parent_chunks)

    def _evaluate_single_item(self, item: BenchmarkItem) -> Dict[str, Any]:
        """单用例原子评测逻辑 (无共享可变状态，100% 线程安全)"""
        t_start = time.perf_counter()

        # --- 步骤 1: 路由判断 ---
        t_r0 = time.perf_counter()
        intent = self.router.route(item.query)
        t_r1 = time.perf_counter()
        router_ms = (t_r1 - t_r0) * 1000

        is_fast_predicted = intent.is_fast_path
        is_target_matched = False
        matched_path = ""
        if item.expected_fast_path and is_fast_predicted:
            matched_path = intent.matched_action.console_path if intent.matched_action else ""
            if item.expected_console_path and matched_path == item.expected_console_path:
                is_target_matched = True

        # --- 步骤 2: 检索与精排 (所有非快轨样本均执行) ---
        retrieval_ms = 0.0
        qa_ms = 0.0
        search_candidates = []
        rerank_results = []
        diag_results = []
        qa_res = None
        is_refused = False
        answer_text = ""

        if not is_fast_predicted or not item.expected_fast_path:
            t_ret0 = time.perf_counter()
            search_candidates = self.hybrid.search(
                item.query,
                top_k=self.config.top_k_candidates,
                user_context=item.user_context
            )
            rerank_results = self.reranker.rerank(item.query, search_candidates, top_n=self.config.top_n_rerank)

            # 并发执行动态诊断任务
            if intent.diagnostic_tasks:
                diag_results = self.diagnostic_registry.execute_tasks_parallel(intent.diagnostic_tasks)

            t_ret1 = time.perf_counter()
            retrieval_ms = (t_ret1 - t_ret0) * 1000

            # --- 步骤 3: 问答生成与归因 ---
            t_qa0 = time.perf_counter()
            qa_res = self.qa_engine.generate_grounded_answer(item.query, rerank_results, diagnostic_results=diag_results)
            t_qa1 = time.perf_counter()
            qa_ms = (t_qa1 - t_qa0) * 1000

            answer_text = qa_res.get("answer", "")
            if "未检索到" in answer_text or "无法解答" in answer_text or not rerank_results:
                is_refused = True

        t_end = time.perf_counter()
        e2e_ms = (t_end - t_start) * 1000

        # --- 检索评测 (检查 Search Candidates 中的排名命中) ---
        found_rank = 0
        if item.target_keywords:
            for rank_idx, cand in enumerate(search_candidates, start=1):
                al = cand.chunk.action_link
                al_text = f"{al.cli_command or ''} {al.required_permission or ''} {al.console_path}" if al else ""
                cand_text = f"{cand.chunk.title} {cand.chunk.contextual_prefix} {cand.chunk.raw_content} {al_text}".lower()
                if any(kw.lower() in cand_text for kw in item.target_keywords):
                    found_rank = rank_idx
                    break

        # --- 问答真实归因评测 ---
        has_grounded_citation = False
        if item.category in ["rag_qa", "rbac_action"]:
            answer_text = qa_res.get("answer", "") if qa_res else ""
            if qa_res and qa_res.get("citations") and bool(re.search(r"\[Doc \d+\]", answer_text)):
                has_grounded_citation = True

        # --- 负向拒答防幻觉评测 ---
        is_refusal_pass = False
        if item.should_refuse:
            if len(rerank_results) == 0 or is_refused:
                is_refusal_pass = True

        # --- 判定该 Case 最终 Status (PASS / FAIL) ---
        case_status = "PASS"
        failure_reasons = []

        if item.category == "fast_track":
            if not (is_fast_predicted and is_target_matched):
                case_status = "FAIL"
                failure_reasons.append(f"路由未命中预期路径: 预测={matched_path}, 期望={item.expected_console_path}")
        elif item.category in ["rag_qa", "rbac_action"]:
            if found_rank == 0 or found_rank > 3:
                case_status = "FAIL"
                failure_reasons.append(f"前3召回脱靶: 实际命中Rank={found_rank}")
            if len(rerank_results) == 0:
                case_status = "FAIL"
                failure_reasons.append("重排置信度过低被全部过滤")
            if not has_grounded_citation:
                case_status = "FAIL"
                failure_reasons.append("回答缺少标准溯源引用[Doc N]")
        elif item.category == "out_of_domain":
            if not is_refusal_pass:
                case_status = "FAIL"
                failure_reasons.append("越界问题未成功触发防幻觉拒答")

        case_detail = {
            "id": item.item_id,
            "category": item.category,
            "query": item.query,
            "status": case_status,
            "failure_reasons": failure_reasons,
            "predicted_fast": is_fast_predicted,
            "expected_fast": item.expected_fast_path,
            "matched_path": matched_path,
            "expected_path": item.expected_console_path,
            "found_rank": found_rank,
            "rerank_top_score": rerank_results[0].relevance_score if rerank_results else 0.0,
            "citations_count": len(qa_res.get("citations", [])) if qa_res else 0,
            "refused": is_refused,
            "answer": answer_text,
            "latency_ms": {
                "router": round(router_ms, 2),
                "retrieval": round(retrieval_ms, 2),
                "qa": round(qa_ms, 2),
                "e2e": round(e2e_ms, 2)
            }
        }

        return {
            "item": item,
            "case_detail": case_detail,
            "router_ms": router_ms,
            "retrieval_ms": retrieval_ms,
            "qa_ms": qa_ms,
            "e2e_ms": e2e_ms,
            "is_fast_predicted": is_fast_predicted,
            "is_target_matched": is_target_matched,
            "found_rank": found_rank,
            "rerank_passed": bool(rerank_results),
            "has_grounded_citation": has_grounded_citation,
            "is_refusal_pass": is_refusal_pass,
        }

    def run_eval(
        self,
        items: List[BenchmarkItem],
        tag: str = "",
        dataset_name: str = "",
        concurrency: int = 5,
        verbose_progress: bool = True
    ) -> Dict[str, Any]:
        """执行端到端自动化质量评测并计算统计量 (支持高并发执行与实时进度看板)"""
        branch, commit = get_git_info()
        now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_items = len(items)
        results: List[Optional[Dict[str, Any]]] = [None] * total_items

        if verbose_progress:
            print(f"-> 启动并发评估引擎: 目标用例数={total_items}, 并发工作线程={concurrency}")

        start_all = time.perf_counter()
        completed_count = 0

        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                future_to_idx = {
                    executor.submit(self._evaluate_single_item, item): idx
                    for idx, item in enumerate(items)
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    res = future.result()
                    results[idx] = res
                    completed_count += 1
                    if verbose_progress:
                        c_stat = res["case_detail"]["status"]
                        e2e_s = res["e2e_ms"] / 1000.0
                        print(f"   [{completed_count:2d}/{total_items}] 用例 {res['item'].item_id:<12} | 耗时: {e2e_s:5.2f}s | 状态: {c_stat}")
        else:
            for idx, item in enumerate(items):
                res = self._evaluate_single_item(item)
                results[idx] = res
                completed_count += 1
                if verbose_progress:
                    c_stat = res["case_detail"]["status"]
                    e2e_s = res["e2e_ms"] / 1000.0
                    print(f"   [{completed_count:2d}/{total_items}] 用例 {res['item'].item_id:<12} | 耗时: {e2e_s:5.2f}s | 状态: {c_stat}")

        total_elapsed_s = time.perf_counter() - start_all
        if verbose_progress:
            print(f"-> 全量用例评估完成，总耗时: {total_elapsed_s:.2f}s\n")

        router_latencies: List[float] = []
        retrieval_latencies: List[float] = []
        qa_latencies: List[float] = []
        e2e_latencies: List[float] = []

        # 1. 路由指标计数
        routing_total = 0
        routing_correct_decision = 0
        fast_path_expected_count = 0
        fast_path_predicted_count = 0
        fast_path_true_positive = 0
        fast_path_target_match = 0

        # 2. 检索指标计数 (针对具有 target_keywords 的样本)
        retrieval_eval_count = 0
        hit_top1_count = 0
        hit_top3_count = 0
        hit_top5_count = 0
        reciprocal_ranks: List[float] = []
        rerank_pass_count = 0

        # 3. 生成与防幻觉指标计数
        grounded_citation_count = 0
        qa_eval_count = 0
        refusal_correct_count = 0
        refusal_eval_count = 0

        detail_cases: List[Dict[str, Any]] = []

        for res in results:
            if not res:
                continue
            item = res["item"]
            detail_cases.append(res["case_detail"])

            router_latencies.append(res["router_ms"])
            if res["retrieval_ms"] > 0:
                retrieval_latencies.append(res["retrieval_ms"])
            if res["qa_ms"] > 0:
                qa_latencies.append(res["qa_ms"])
            e2e_latencies.append(res["e2e_ms"])

            # 路由指标
            routing_total += 1
            if res["is_fast_predicted"] == item.expected_fast_path:
                routing_correct_decision += 1
            if item.expected_fast_path:
                fast_path_expected_count += 1
            if res["is_fast_predicted"]:
                fast_path_predicted_count += 1
            if item.expected_fast_path and res["is_fast_predicted"]:
                fast_path_true_positive += 1
                if res["is_target_matched"]:
                    fast_path_target_match += 1

            # 检索指标
            if item.target_keywords:
                retrieval_eval_count += 1
                if res["rerank_passed"]:
                    rerank_pass_count += 1
                found_rank = res["found_rank"]
                if found_rank == 1:
                    hit_top1_count += 1
                if 1 <= found_rank <= 3:
                    hit_top3_count += 1
                if 1 <= found_rank <= 5:
                    hit_top5_count += 1
                reciprocal_ranks.append((1.0 / found_rank) if found_rank > 0 else 0.0)

            # 问答与拒答指标
            if item.category in ["rag_qa", "rbac_action"]:
                qa_eval_count += 1
                if res["has_grounded_citation"]:
                    grounded_citation_count += 1

            if item.should_refuse:
                refusal_eval_count += 1
                if res["is_refusal_pass"]:
                    refusal_correct_count += 1

        # --- 计算统计指标 ---
        fast_precision = (fast_path_true_positive / fast_path_predicted_count) if fast_path_predicted_count > 0 else 1.0
        fast_recall = (fast_path_true_positive / fast_path_expected_count) if fast_path_expected_count > 0 else 1.0
        fast_f1 = (2 * fast_precision * fast_recall / (fast_precision + fast_recall)) if (fast_precision + fast_recall) > 0 else 0.0
        routing_acc = routing_correct_decision / routing_total if routing_total > 0 else 0.0
        path_match_acc = (fast_path_target_match / fast_path_expected_count) if fast_path_expected_count > 0 else 1.0

        hit_rate_top1 = (hit_top1_count / retrieval_eval_count) if retrieval_eval_count > 0 else 0.0
        hit_rate_top3 = (hit_top3_count / retrieval_eval_count) if retrieval_eval_count > 0 else 0.0
        hit_rate_top5 = (hit_top5_count / retrieval_eval_count) if retrieval_eval_count > 0 else 0.0
        mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
        rerank_retention_rate = (rerank_pass_count / retrieval_eval_count) if retrieval_eval_count > 0 else 0.0

        grounded_ratio = (grounded_citation_count / qa_eval_count) if qa_eval_count > 0 else 0.0
        refusal_accuracy = (refusal_correct_count / refusal_eval_count) if refusal_eval_count > 0 else 0.0

        def calc_percentiles(arr: List[float]) -> Dict[str, float]:
            if not arr:
                return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "avg": 0.0}
            sorted_arr = sorted(arr)
            n = len(sorted_arr)
            return {
                "p50": round(statistics.median(sorted_arr), 2),
                "p90": round(sorted_arr[min(int(n * 0.9), n - 1)], 2),
                "p99": round(sorted_arr[min(int(n * 0.99), n - 1)], 2),
                "avg": round(statistics.mean(sorted_arr), 2)
            }

        snapshot_id = f"eval_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        llm_client = self.qa_engine.llm_client
        return {
            "metadata": {
                "snapshot_id": snapshot_id,
                "timestamp": now_iso,
                "tag": tag or "unspecified",
                "git_branch": branch,
                "git_commit": commit,
                "dataset_source": dataset_name or "in_memory",
                "total_samples": len(items),
                "llm_provider": llm_client.provider_name,
                "llm_model": llm_client.model_name,
                "llm_base_url": llm_client.base_url,
                "is_simulated": llm_client.is_simulated
            },
            "summary": {
                "routing": {
                    "overall_accuracy": round(routing_acc, 4),
                    "fast_path_precision": round(fast_precision, 4),
                    "fast_path_recall": round(fast_recall, 4),
                    "fast_path_f1": round(fast_f1, 4),
                    "target_path_match_rate": round(path_match_acc, 4)
                },
                "retrieval": {
                    "evaluated_queries": retrieval_eval_count,
                    "hit_rate_at_1": round(hit_rate_top1, 4),
                    "hit_rate_at_3": round(hit_rate_top3, 4),
                    "hit_rate_at_5": round(hit_rate_top5, 4),
                    "mean_reciprocal_rank_mrr": round(mrr, 4),
                    "rerank_retention_rate": round(rerank_retention_rate, 4)
                },
                "generation_and_safety": {
                    "qa_evaluated_queries": qa_eval_count,
                    "grounded_citation_rate": round(grounded_ratio, 4),
                    "out_of_domain_refusal_rate": round(refusal_accuracy, 4)
                },
                "latency_ms": {
                    "router": calc_percentiles(router_latencies),
                    "retrieval": calc_percentiles(retrieval_latencies),
                    "qa_generation": calc_percentiles(qa_latencies),
                    "end_to_end": calc_percentiles(e2e_latencies)
                }
            },
            "cases": detail_cases
        }


# =============================================================================
# 四、 快照管理与历史追溯 (Snapshot Manager)
# =============================================================================
class SnapshotManager:
    """管理 eval_history/ 目录下的评测快照持久化与检索"""

    def __init__(self, history_dir: str):
        self.history_dir = os.path.join(project_root, history_dir)
        os.makedirs(self.history_dir, exist_ok=True)

    def save_snapshot(self, result: Dict[str, Any]) -> str:
        """持久化单次运行快照为 JSON 文件，并同步写入 latest.json"""
        snapshot_id = result["metadata"]["snapshot_id"]
        filename = f"{snapshot_id}.json"
        target_path = os.path.join(self.history_dir, filename)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        latest_path = os.path.join(self.history_dir, "latest.json")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return target_path

    def list_history(self) -> List[Dict[str, Any]]:
        """获取所有历史快照的元数据简报"""
        pattern = os.path.join(self.history_dir, "eval_*.json")
        files = sorted(glob.glob(pattern), reverse=True)

        history_list = []
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                summ = data.get("summary", {})
                ret = summ.get("retrieval", {})
                rout = summ.get("routing", {})
                history_list.append({
                    "file": os.path.basename(fp),
                    "path": fp,
                    "timestamp": meta.get("timestamp", "unknown"),
                    "tag": meta.get("tag", "none"),
                    "commit": meta.get("git_commit", "unknown"),
                    "routing_acc": rout.get("overall_accuracy", 0.0),
                    "hit_rate_at_3": ret.get("hit_rate_at_3", 0.0),
                    "mrr": ret.get("mean_reciprocal_rank_mrr", 0.0)
                })
            except Exception:
                continue
        return history_list

    def load_snapshot(self, target: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """加载指定路径、快照名或最新快照"""
        if not target or target == "latest":
            latest_path = os.path.join(self.history_dir, "latest.json")
            if os.path.exists(latest_path):
                with open(latest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            history = self.list_history()
            if history:
                with open(history[0]["path"], "r", encoding="utf-8") as f:
                    return json.load(f)
            return None

        if os.path.exists(target):
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)

        candidate = os.path.join(self.history_dir, target)
        if not candidate.endswith(".json"):
            candidate += ".json"
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)

        return None

    def get_previous_snapshot(self, exclude_snapshot_id: str) -> Optional[Dict[str, Any]]:
        """获取排除指定 ID 之外的最近一个历史快照（用于自动对比）"""
        history = self.list_history()
        for h in history:
            fn = h["file"].replace(".json", "")
            if fn != exclude_snapshot_id:
                return self.load_snapshot(h["path"])
        return None


# =============================================================================
# 五、 自动化 Diff 对比与退化检测引擎 (Benchmark Differ)
# =============================================================================
class BenchmarkDiffer:
    """负责两组评测快照的逐项对比与退化告警"""

    @staticmethod
    def compare(current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
        """对比两个版本的聚合指标与用例级别状态"""
        curr_meta = current.get("metadata", {})
        base_meta = baseline.get("metadata", {})

        curr_summ = current.get("summary", {})
        base_summ = baseline.get("summary", {})

        metrics_diff = []

        def add_metric(category: str, name: str, key_path: List[str], is_percentage: bool = True, higher_is_better: bool = True):
            v_curr = curr_summ
            for k in key_path:
                v_curr = v_curr.get(k, 0.0) if isinstance(v_curr, dict) else 0.0

            v_base = base_summ
            for k in key_path:
                v_base = v_base.get(k, 0.0) if isinstance(v_base, dict) else 0.0

            delta = v_curr - v_base
            fmt = "{:.1f}%" if is_percentage else "{:.3f}"
            delta_fmt = "{:+.1f}%" if is_percentage else "{:+.3f}"

            multiplier = 100 if is_percentage else 1
            curr_str = fmt.format(v_curr * multiplier)
            base_str = fmt.format(v_base * multiplier)
            delta_str = delta_fmt.format(delta * multiplier)

            status = "FLAT"
            if abs(delta) > 0.0001:
                if (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
                    status = "IMPROVED"
                else:
                    status = "REGRESSED"

            metrics_diff.append({
                "category": category,
                "name": name,
                "baseline": base_str,
                "current": curr_str,
                "delta": delta_str,
                "status": status
            })

        add_metric("路由", "整体分流准确率", ["routing", "overall_accuracy"])
        add_metric("路由", "快轨 F1 得分", ["routing", "fast_path_f1"])
        add_metric("路由", "控制台路径匹配率", ["routing", "target_path_match_rate"])

        add_metric("检索", "Hit Rate @ 1", ["retrieval", "hit_rate_at_1"])
        add_metric("检索", "Hit Rate @ 3", ["retrieval", "hit_rate_at_3"])
        add_metric("检索", "MRR (平均倒数排名)", ["retrieval", "mean_reciprocal_rank_mrr"], is_percentage=False)
        add_metric("检索", "重排置信保留率", ["retrieval", "rerank_retention_rate"])

        add_metric("生成", "真实溯源标注率", ["generation_and_safety", "grounded_citation_rate"])
        add_metric("安全", "负向越界拒答率", ["generation_and_safety", "out_of_domain_refusal_rate"])

        add_metric("耗时", "端到端 P50 延迟(ms)", ["latency_ms", "end_to_end", "p50"], is_percentage=False, higher_is_better=False)
        add_metric("耗时", "端到端 P90 延迟(ms)", ["latency_ms", "end_to_end", "p90"], is_percentage=False, higher_is_better=False)

        curr_cases = {c["id"]: c for c in current.get("cases", [])}
        base_cases = {c["id"]: c for c in baseline.get("cases", [])}

        regressions = []
        improvements = []

        for cid, c_curr in curr_cases.items():
            c_base = base_cases.get(cid)
            if not c_base:
                continue

            b_stat = c_base.get("status", "UNKNOWN")
            c_stat = c_curr.get("status", "UNKNOWN")

            if b_stat == "PASS" and c_stat == "FAIL":
                regressions.append({
                    "id": cid,
                    "query": c_curr["query"],
                    "category": c_curr["category"],
                    "baseline_status": b_stat,
                    "current_status": c_stat,
                    "reasons": c_curr.get("failure_reasons", [])
                })
            elif b_stat == "FAIL" and c_stat == "PASS":
                improvements.append({
                    "id": cid,
                    "query": c_curr["query"],
                    "category": c_curr["category"],
                    "baseline_status": b_stat,
                    "current_status": c_stat
                })

        return {
            "baseline_meta": base_meta,
            "current_meta": curr_meta,
            "metrics_diff": metrics_diff,
            "regressions": regressions,
            "improvements": improvements,
            "has_regression": len(regressions) > 0
        }

    @staticmethod
    def format_diff_report(diff_res: Dict[str, Any]) -> str:
        """格式化比对看板为标准 Markdown"""
        b_meta = diff_res["baseline_meta"]
        c_meta = diff_res["current_meta"]

        lines = [
            "# 自动化评测版本比对与退化审计报告 (Regression Diff Report)\n",
            f"- **当前版本 (Current)**: `{c_meta.get('snapshot_id')}` (Tag: `{c_meta.get('tag')}`, Commit: `{c_meta.get('git_commit')}`, 时间: {c_meta.get('timestamp')})",
            f"- **对比基准 (Baseline)**: `{b_meta.get('snapshot_id')}` (Tag: `{b_meta.get('tag')}`, Commit: `{b_meta.get('git_commit')}`, 时间: {b_meta.get('timestamp')})",
            "\n---\n",
            "## 一、 核心指标变化看板 (Metrics Delta Dashboard)\n",
            "| 模块 | 度量指标 | 基线版本 (Baseline) | 当前版本 (Current) | 差异变化 (Delta) | 状态 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for m in diff_res["metrics_diff"]:
            flag = "FLAT"
            if m["status"] == "IMPROVED":
                flag = "IMPROVED (+)"
            elif m["status"] == "REGRESSED":
                flag = "REGRESSED (-)"
            lines.append(f"| **{m['category']}** | {m['name']} | {m['baseline']} | **{m['current']}** | `{m['delta']}` | {flag} |")

        lines.append("\n---\n")

        regs = diff_res["regressions"]
        lines.append(f"## 二、 退化用例审计 (Regressions Detected: {len(regs)})\n")
        if not regs:
            lines.append("> [PASS] 未检测到任何退化用例！系统在当前改动下保持 100% 质量稳定。\n")
        else:
            lines.append("> [ALERT] 检测到用例性能退化，请在合并前重点修复以下案例：\n")
            lines.append("| 用例 ID | 场景分类 | 提问 Query | 退化原因 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for r in regs:
                r_reason = "；".join(r["reasons"])
                lines.append(f"| `{r['id']}` | {r['category']} | {r['query']} | **{r_reason}** |")
            lines.append("")

        imps = diff_res["improvements"]
        lines.append(f"## 三、 修复与提升用例 (Fixed / Improvements: {len(imps)})\n")
        if not imps:
            lines.append("> 本次运行未发生原本失败用例的翻转。\n")
        else:
            lines.append("| 用例 ID | 场景分类 | 提问 Query | 状态提升 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for im in imps:
                lines.append(f"| `{im['id']}` | {im['category']} | {im['query']} | FAIL -> **PASS** |")
            lines.append("")

        return "\n".join(lines)


def format_markdown_report(result: Dict[str, Any], config: EvalConfig) -> str:
    """将评测结果格式化为标准 Markdown 评测报告"""
    m = result["metadata"]
    s = result["summary"]
    r_lat = s["latency_ms"]["router"]
    ret_lat = s["latency_ms"]["retrieval"]
    e2e_lat = s["latency_ms"]["end_to_end"]
    env_desc = "确定性本地模拟引擎 (离线无网保底)" if m.get("is_simulated", False) else f"真实外部模型调用 ({m.get('llm_provider', 'unknown')})"

    report = f"""# 知识库与控制台 Agent 自动化质量评测基准报告 (Offline Eval Benchmark)

- **快照编号**: `{m["snapshot_id"]}` (Tag: `{m["tag"]}`, Commit: `{m["git_commit"]}`)
- **评测时间**: {m["timestamp"]}
- **数据来源**: `{m.get("dataset_source", "unknown")}` (共 {m["total_samples"]} 条用例)
- **大模型驱动**: `{m.get("llm_provider", "unknown")}` (模型: `{m.get("llm_model", "unknown")}`)
- **接口服务端点**: `{m.get("llm_base_url", "default")}`
- **运行环境模式**: {env_desc}

---

## 一、 核心指标总览表 (Executive Dashboard)

| 评估维度 | 核心度量指标 (Metric) | 测量值 | 工业基准线要求 | 判定状态 |
| :--- | :--- | :--- | :--- | :--- |
| **控制台意图路由** | 整体分流准确率 (Accuracy) | **{s["routing"]["overall_accuracy"] * 100:.1f}%** | ≥ {config.routing_overall_acc_min * 100:.1f}% | {"PASS" if s["routing"]["overall_accuracy"] >= config.routing_overall_acc_min else "WARN"} |
| | 快轨 F1 得分 (Fast-Path F1) | **{s["routing"]["fast_path_f1"] * 100:.1f}%** | ≥ {config.routing_fast_f1_min * 100:.1f}% | {"PASS" if s["routing"]["fast_path_f1"] >= config.routing_fast_f1_min else "WARN"} |
| | 控制台页面直达匹配率 (Path Match) | **{s["routing"]["target_path_match_rate"] * 100:.1f}%** | ≥ {config.routing_path_match_min * 100:.1f}% | {"PASS" if s["routing"]["target_path_match_rate"] >= config.routing_path_match_min else "WARN"} |
| **混合检索与精排** | **Hit Rate @ 1** (首条命中率) | **{s["retrieval"]["hit_rate_at_1"] * 100:.1f}%** | ≥ {config.hit_rate_at_1_min * 100:.1f}% | {"PASS" if s["retrieval"]["hit_rate_at_1"] >= config.hit_rate_at_1_min else "WARN"} |
| | **Hit Rate @ 3** (前3命中率) | **{s["retrieval"]["hit_rate_at_3"] * 100:.1f}%** | ≥ {config.hit_rate_at_3_min * 100:.1f}% | {"PASS" if s["retrieval"]["hit_rate_at_3"] >= config.hit_rate_at_3_min else "WARN"} |
| | **MRR** (平均倒数排名) | **{s["retrieval"]["mean_reciprocal_rank_mrr"]:.3f}** | ≥ {config.mrr_min:.3f} | {"PASS" if s["retrieval"]["mean_reciprocal_rank_mrr"] >= config.mrr_min else "WARN"} |
| | 重排置信度保留率 | **{s["retrieval"]["rerank_retention_rate"] * 100:.1f}%** | ≥ {config.rerank_retention_min * 100:.1f}% | {"PASS" if s["retrieval"]["rerank_retention_rate"] >= config.rerank_retention_min else "WARN"} |
| **回答质量与防幻觉** | 真实引用标注率 (Grounded Citation) | **{s["generation_and_safety"]["grounded_citation_rate"] * 100:.1f}%** | 100.0% | {"PASS" if s["generation_and_safety"]["grounded_citation_rate"] >= config.grounded_citation_min else "WARN"} |
| | 负向越界拒答率 (Safety Refusal) | **{s["generation_and_safety"]["out_of_domain_refusal_rate"] * 100:.1f}%** | 100.0% | {"PASS" if s["generation_and_safety"]["out_of_domain_refusal_rate"] >= config.out_of_domain_refusal_min else "WARN"} |

---

## 二、 耗时与延迟分布 (Latency Distribution)

| 阶段组件 | P50 (中位数) | P90 | P99 | 平均耗时 (Avg) |
| :--- | :--- | :--- | :--- | :--- |
| **控制台意图路由器** | {r_lat["p50"]:.2f} ms | {r_lat["p90"]:.2f} ms | {r_lat["p99"]:.2f} ms | {r_lat["avg"]:.2f} ms |
| **混合召回 + Cross 重排** | {ret_lat["p50"]:.2f} ms | {ret_lat["p90"]:.2f} ms | {ret_lat["p99"]:.2f} ms | {ret_lat["avg"]:.2f} ms |
| **端到端全链路 (E2E)** | {e2e_lat["p50"]:.2f} ms | {e2e_lat["p90"]:.2f} ms | {e2e_lat["p99"]:.2f} ms | {e2e_lat["avg"]:.2f} ms |

---

## 三、 分场景用例测试摘要

```
- 样本总量: {m["total_samples"]} 条有效评估用例
- 数据来源: {m.get("dataset_source", "unknown")}
- 路由与快轨: 平均耗时 {r_lat["avg"]:.2f} ms，快慢轨准确分流
- 知识问答与归因: 准确检索上下文并附带 [Doc 编号] 真实溯源
```
"""
    return report


class TestBenchmarkSuite(unittest.TestCase):
    """供 CI/CD 或本地自动化测试断言的 TestCase"""

    @classmethod
    def setUpClass(cls):
        cls.config = EvalConfig.load()
        dataset_path = os.path.join(project_root, cls.config.default_dataset)
        cls.items = DatasetLoader.load_dataset(dataset_path)
        cls.evaluator = BenchmarkEvaluator(cls.config)
        cls.eval_results = cls.evaluator.run_eval(
            cls.items,
            tag="ci_test",
            dataset_name=os.path.basename(dataset_path),
            concurrency=5,
            verbose_progress=False
        )

    def test_routing_performance(self):
        routing = self.eval_results["summary"]["routing"]
        self.assertGreaterEqual(routing["overall_accuracy"], self.config.routing_overall_acc_min, "控制台路由整体准确率应达标")
        self.assertGreaterEqual(routing["fast_path_f1"], self.config.routing_fast_f1_min, "快轨 F1 分数应达标")
        self.assertGreaterEqual(routing["target_path_match_rate"], self.config.routing_path_match_min, "快轨路径匹配率应达标")

    def test_retrieval_hit_rate(self):
        retrieval = self.eval_results["summary"]["retrieval"]
        self.assertGreaterEqual(retrieval["hit_rate_at_3"], self.config.hit_rate_at_3_min, "Hit Rate@3 召回率应达标")
        self.assertGreaterEqual(retrieval["mean_reciprocal_rank_mrr"], self.config.mrr_min, "MRR 应达标")

    def test_safety_refusal(self):
        safety = self.eval_results["summary"]["generation_and_safety"]
        self.assertEqual(safety["out_of_domain_refusal_rate"], self.config.out_of_domain_refusal_min, "负向越界问题拒答率必须达标")

    def test_grounded_citation(self):
        safety = self.eval_results["summary"]["generation_and_safety"]
        self.assertGreaterEqual(safety["grounded_citation_rate"], self.config.grounded_citation_min, "知识问答溯源引用率应达标")


def main():
    parser = argparse.ArgumentParser(description="知识库 Agent 自动化质量评测基准与版本追溯引擎")
    parser.add_argument("--config", type=str, default="", help="评测配置文件路径 (默认: eval_config.json)")
    parser.add_argument("--dataset", type=str, default="", help="指定测试用例数据集路径 (支持 .json 或 .jsonl，兼容模型生成格式)")
    parser.add_argument("--report", action="store_true", help="是否输出并保存 Markdown 评测报告")
    parser.add_argument("--output", type=str, default="", help="报告输出文件路径 (默认使用配置文件设置)")
    parser.add_argument("--tag", type=str, default="", help="为本次评测打标签 (如: baseline, synthetic_v1)")
    parser.add_argument("--no-save", action="store_true", help="跳过快照持久化到 eval_history/")
    parser.add_argument("--history", action="store_true", help="查看所有历史快照版本简报")
    parser.add_argument("--diff", nargs="?", const="auto", default=None, help="对比版本: 可不跟参数(自动对比上一个快照)，或指定快照文件/ID")
    parser.add_argument("--diff-report", type=str, default="", help="保存比对差异为 Markdown 文件")
    parser.add_argument("--fail-on-regression", action="store_true", help="若检测到退化用例则退出码返回 1 (门禁检查)")
    parser.add_argument("--test", action="store_true", help="以 unittest 模式执行并返回退出码")
    parser.add_argument("--concurrency", "-c", type=int, default=5, help="并发评估工作线程数 (默认: 5)")
    args = parser.parse_args()

    # 1. 单元测试模式
    if args.test:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestBenchmarkSuite)
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        sys.exit(0 if res.wasSuccessful() else 1)

    # 2. 加载配置
    config = EvalConfig.load(args.config if args.config else None)
    mgr = SnapshotManager(config.history_dir)

    # 3. 查看历史列表模式
    if args.history:
        history = mgr.list_history()
        print("\n" + "=" * 32 + " 评测快照历史追溯档案 (eval_history/) " + "=" * 32)
        if not history:
            print("目前暂无持久化快照，可先运行一次 python3 eval_benchmark.py 生成快照。")
            return
        print(f"{'快照文件名':<28} | {'标签 (Tag)':<15} | {'Commit':<10} | {'路由准确率':<10} | {'Hit@3':<8} | {'MRR':<8} | {'评测时间'}")
        print("-" * 105)
        for h in history:
            print(f"{h['file']:<28} | {h['tag']:<15} | {h['commit']:<10} | {h['routing_acc']*100:<9.1f}% | {h['hit_rate_at_3']*100:<7.1f}% | {h['mrr']:<8.3f} | {h['timestamp']}")
        print("")
        return

    # 4. 加载测试数据集 (解耦数据源)
    dataset_file = args.dataset if args.dataset else config.default_dataset
    dataset_path = os.path.join(project_root, dataset_file) if not os.path.isabs(dataset_file) else dataset_file

    try:
        items = DatasetLoader.load_dataset(dataset_path)
    except Exception as e:
        print(f"\n[数据加载错误]: 无法解析数据集文件 {dataset_path} -> {e}")
        sys.exit(1)

    dataset_name = os.path.basename(dataset_path)
    print("\n" + "=" * 32 + " 开始执行知识库 Agent 自动化质量评测 " + "=" * 32)
    print(f"-> 评测配置加载就绪: {args.config or 'eval_config.json'}")
    print(f"-> 测试数据集加载成功: {dataset_name} (有效用例: {len(items)} 条)")

    # 5. 运行评测
    evaluator = BenchmarkEvaluator(config)
    print(f"-> 知识库载入完毕: {len(evaluator.parent_chunks)} 个父块, {len(evaluator.child_chunks)} 个子块")

    res = evaluator.run_eval(items, tag=args.tag, dataset_name=dataset_name, concurrency=args.concurrency)
    current_snapshot_id = res["metadata"]["snapshot_id"]

    # 持久化快照
    if not args.no_save:
        saved_path = mgr.save_snapshot(res)
        print(f"-> [快照持久化就绪]: {saved_path}")

    # 打印当前结果
    md_content = format_markdown_report(res, config)
    print(md_content)

    if args.report:
        report_file = args.output if args.output else config.default_report
        out_path = os.path.join(project_root, report_file) if not os.path.isabs(report_file) else report_file
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"\n[OK] 评测报告已成功导出至: {out_path}\n")

    # 6. 执行 Diff 比对逻辑
    has_regressions = False
    if args.diff:
        baseline_data = None
        if args.diff == "auto":
            baseline_data = mgr.get_previous_snapshot(current_snapshot_id)
            if not baseline_data:
                print("\n[Diff 提示]: 未发现上一个历史快照版本，本次运行将作为历史基线 (Baseline)。\n")
        else:
            baseline_data = mgr.load_snapshot(args.diff)
            if not baseline_data:
                print(f"\n[Diff 错误]: 无法找到指定的基线快照: {args.diff}\n")

        if baseline_data:
            diff_result = BenchmarkDiffer.compare(res, baseline_data)
            diff_md = BenchmarkDiffer.format_diff_report(diff_result)
            print("\n" + "=" * 32 + " 版本差异比对看板 " + "=" * 32)
            print(diff_md)

            has_regressions = diff_result["has_regression"]

            if args.diff_report:
                diff_report_path = os.path.join(project_root, args.diff_report) if not os.path.isabs(args.diff_report) else args.diff_report
                with open(diff_report_path, "w", encoding="utf-8") as f:
                    f.write(diff_md)
                print(f"[OK] 比对差异报告已保存至: {diff_report_path}\n")

    # 7. 质量门禁检查
    if args.fail_on_regression and has_regressions:
        print("[CI 门禁失败]: 检测到评测用例发生退化，阻断当前流水线！")
        sys.exit(1)


if __name__ == "__main__":
    main()
