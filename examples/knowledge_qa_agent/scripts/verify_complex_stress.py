"""复杂工业压力场景端到端评估套件 (Complex Industrial Stress Benchmark Suite)

涵盖四类高难度真实生产挑战：
1. 跨多部规程联合多跳推断 (Multi-hop Reasoning: DL/T 722 + DL/T 596)
2. 原始测点数值计算与三比值编码动态推导 (Calculated Code Mapping)
3. 高相似同类设备强干扰负样本抗混淆 (Hard Negatives: 主变 vs 互感器 PT/CT)
4. 新旧规程版本修订与冲突时效性仲裁 (Temporal Conflict Resolution)
"""
import os
import sys
import time
import json
import re
from typing import List, Dict, Any

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.ingestion.parser import UniversalDocumentParser
from src.ingestion.chunker import ContextualChunker
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseSemanticRetriever
from src.retrieval.hybrid import HybridRRFRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.navigation.router import IntentRouter
from src.agent.qa_engine import KnowledgeAgentEngine
from src.agent.tools.diagnostic_registry import DiagnosticToolRegistry
from src.agent.llm_client import LiteLLMClient, MockLLMClient
from eval_benchmark import BenchmarkEvaluator, EvalConfig, DatasetLoader, BenchmarkItem


def run_complex_stress_benchmark():
    print("=" * 60)
    print("【复杂工业压力场景基准测试】：多规程多跳、计算映射与强干扰排障")
    print("=" * 60)

    # 1. 结构化解析两部互补工业标准规程
    parser = UniversalDocumentParser()
    doc_paths = [
        os.path.join(project_root, "data", "industrial_transformer_dlt722.md"),
        os.path.join(project_root, "data", "industrial_preventive_test_dlt596.md")
    ]

    all_sections = []
    for dp in doc_paths:
        sec = parser.parse_sections(dp)
        print(f"-> 成功解析规程 [{os.path.basename(dp)}]: {len(sec)} 个结构化章节")
        all_sections.extend(sec)

    # 2. 统一构建 Small-to-Big 父子切片池与面包屑
    chunker = ContextualChunker(child_max_chars=260, overlap_chars=40)
    parent_chunks, child_chunks = chunker.build_parent_and_child_chunks(all_sections, doc_id="power_multi_standards")
    print(f"-> 生成融合父块 (Parent Chunks): {len(parent_chunks)} 个")
    print(f"-> 生成细粒度子块 (Child Chunks): {len(child_chunks)} 个")

    # 3. 拟合双路混合检索与精排重排器
    bm25 = BM25Retriever()
    bm25.fit(child_chunks)

    dense = DenseSemanticRetriever()
    dense.fit(child_chunks)

    hybrid = HybridRRFRetriever(bm25, dense, rrf_k=60)
    reranker = CrossEncoderReranker(min_relevance_threshold=0.15)
    router = IntentRouter(child_chunks)

    # 4. 初始化 QA 引擎与统一大模型
    try:
        llm = LiteLLMClient()
    except RuntimeError:
        llm = MockLLMClient()
    qa_engine = KnowledgeAgentEngine(parent_chunks=parent_chunks, llm_client=llm)

    print(f"\n【当前生效模型】: {llm.model_name} (底层驱动: {llm.provider_name}, 模拟模式: {llm.is_simulated})")

    # 5. 加载高难度复杂压力测试集
    eval_file = os.path.join(project_root, "eval_data", "complex_stress_dataset.json")
    with open(eval_file, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    test_items = [
        BenchmarkItem(
            item_id=it["id"],
            category=it["category"],
            query=it["query"],
            target_keywords=it["target_keywords"],
            expected_fast_path=it.get("expected_fast_path", False),
            expected_console_path=it.get("expected_console_path"),
            should_refuse=it.get("should_refuse", False)
        )
        for it in raw_items
    ]

    eval_config = EvalConfig(
        default_dataset=eval_file,
        data_dir=os.path.join(project_root, "data"),
        default_report=os.path.join(project_root, "reports", "complex_stress_report.md")
    )

    evaluator = BenchmarkEvaluator(eval_config)
    evaluator.router = router
    evaluator.hybrid = hybrid
    evaluator.reranker = reranker
    evaluator.qa_engine = qa_engine

    print(f"\n-> 启动复杂压力评估引擎 (总用例数: {len(test_items)})...")
    eval_result = evaluator.run_eval(test_items, tag="complex_stress", dataset_name="Complex_Stress_Suite", concurrency=3)

    print("\n" + "=" * 60)
    print("【复杂压力场景各用例执行详情与模型回复】:")
    print("=" * 60)

    cases = eval_result["cases"]
    pass_count = sum(1 for c in cases if c["status"] == "PASS")

    if llm.is_simulated:
        arch_desc = "(本地离线模拟保底桩，未调用真实在线模型)"
    elif "Qwen3-30B-A3B" in llm.model_name:
        arch_desc = "(架构: 30.5B MoE, 3.3B 激活)"
    else:
        arch_desc = f"(驱动底层: {llm.provider_name})"

    report_lines = [
        "# 复杂工业压力场景（多规程多跳/计算映射/强干扰）评估报告",
        f"\n> **评估时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> **基座模型**: `{llm.model_name}` {arch_desc}  ",
        f"> **综合通过率**: **{pass_count}/{len(cases)} ({pass_count/len(cases)*100:.1f}%)**\n",
        "---",
        "## 一、 复杂场景用例实测全景",
        "\n| 用例 ID | 挑战类型 | 问题摘要 | 状态 | 耗时 | 命中依据 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    challenge_names = {
        "stress_multihop_01": "跨规程多跳联合推断",
        "stress_negative_01": "主变 vs PT 强干扰对比",
        "stress_calculation_01": "数值换算与改良三比值编码",
        "stress_version_01": "新旧规程废止冲突仲裁",
        "stress_negative_02": "CT 互感器抗张冠李戴",
        "stress_multihop_02": "色谱放电与击穿电压两规程确诊"
    }

    for idx, c in enumerate(cases, 1):
        ch_name = challenge_names.get(c["id"], "复杂综合场景")
        print(f"\n[{idx}/{len(cases)}] 用例: {c['id']} ({ch_name})")
        print(f"提问: {c['query']}")
        print(f"状态: {c['status']} | 耗时: {c['latency_ms']['e2e']/1000:.2f}s")
        ans = c.get('answer', '')
        print(f"模型实际回答:\n{ans}")
        print("-" * 50)

        report_lines.append(
            f"| `{c['id']}` | **{ch_name}** | {c['query'][:28]}... | **{c['status']}** | {c['latency_ms']['e2e']/1000:.2f}s | `[Doc N]` 引用: {c['citations_count']} 篇 |"
        )

    report_lines.extend([
        "\n---",
        "## 二、 复杂场景各用例推断与回答剖析",
        ""
    ])

    for c in cases:
        ch_name = challenge_names.get(c["id"], "复杂综合场景")
        report_lines.append(f"### 用例 `{c['id']}`：{ch_name}")
        report_lines.append(f"- **提问**: {c['query']}")
        report_lines.append(f"- **判定**: **{c['status']}** (耗时: {c['latency_ms']['e2e']/1000:.2f}s)")
        ans_text = c.get('answer', '')
        report_lines.append(f"- **模型回答**:\n\n> {ans_text.replace(chr(10), chr(10) + '> ')}\n")

    report_path = os.path.join(project_root, "reports", "complex_stress_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n-> 复杂压力场景评测报告已生成: {report_path}")
    return eval_result


if __name__ == "__main__":
    run_complex_stress_benchmark()
