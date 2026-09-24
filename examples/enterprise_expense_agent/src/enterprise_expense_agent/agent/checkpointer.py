"""持久化检查点组件（Durable Checkpointer）
实现生产级持久化执行（Durable Execution）：
深度集成 LangGraph 官方 BaseCheckpointSaver / MemorySaver 规范：
1. 维护全量拓扑状态、版本通道（Channel Versions）与操作历史（Writes）；
2. 同时生成 .ckpt 二进制快照与人类可读的 .json 审计镜像；
3. 支持进程崩溃（OOM / 宿主机迁移）后的冷启动现场重建与时间旅行。
"""
import os
import json
import pickle
from collections import defaultdict
from typing import Optional, Dict, Any, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# 允许安全反序列化的模块类型白名单（消除 MsgPack 潜在告警）
ALLOWED_MSGPACK_MODULES = [
    # 标准 package 命名空间
    ("enterprise_expense_agent.governance.rbac", "Role"),
    ("enterprise_expense_agent.governance.rbac", "SecurityContext"),
    ("enterprise_expense_agent.agent.schema", "ClaimStatus"),
    ("enterprise_expense_agent.agent.schema", "ValidatedExpenseClaim"),
    ("enterprise_expense_agent.governance.risk_checker", "RiskAssessment"),
    ("enterprise_expense_agent.governance.hitl", "ApprovalTicket"),
    ("enterprise_expense_agent.agent.state", "ExpenseAgentState"),
    # 完整项目路径命名空间
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.governance.rbac", "Role"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.governance.rbac", "SecurityContext"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.agent.schema", "ClaimStatus"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.agent.schema", "ValidatedExpenseClaim"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.governance.risk_checker", "RiskAssessment"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.governance.hitl", "ApprovalTicket"),
    ("examples.enterprise_expense_agent.src.enterprise_expense_agent.agent.state", "ExpenseAgentState"),
    # 向下兼容历史路径
    ("examples.enterprise_expense_agent.governance.rbac", "Role"),
    ("examples.enterprise_expense_agent.governance.rbac", "SecurityContext"),
    ("examples.enterprise_expense_agent.agent.schema", "ClaimStatus"),
    ("examples.enterprise_expense_agent.agent.schema", "ValidatedExpenseClaim"),
    ("examples.enterprise_expense_agent.governance.risk_checker", "RiskAssessment"),
    ("examples.enterprise_expense_agent.governance.hitl", "ApprovalTicket"),
    ("examples.enterprise_expense_agent.agent.state", "ExpenseAgentState"),
]

class LangGraphFileCheckpointer(MemorySaver):
    """文件持久化与内存索引结合的 LangGraph 原生 Checkpointer"""

    def __init__(self, storage_dir: Optional[str] = None):
        serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES)
        super().__init__(serde=serde)

        if storage_dir is None:
            pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            storage_dir = os.path.join(pkg_root, ".runtime_checkpoints")
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _ckpt_file(self, thread_id: str) -> str:
        return os.path.join(self.storage_dir, f"{thread_id}.ckpt")

    def _json_file(self, thread_id: str) -> str:
        return os.path.join(self.storage_dir, f"{thread_id}.json")

    def _load_thread(self, thread_id: str):
        """冷启动时从磁盘恢复指定 thread 的历史检查点索引"""
        if thread_id in self.storage:
            return
        path = self._ckpt_file(thread_id)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self.storage[thread_id] = defaultdict(dict, data.get("storage", {}))
                    for k, v in data.get("writes", {}).items():
                        self.writes[k].update(v)
                    self.blobs.update(data.get("blobs", {}))
            except Exception as e:
                # 容错降级
                pass

    def _save_thread(self, thread_id: str, checkpoint: Optional[Checkpoint] = None):
        """持久化指定 thread 的完整状态与审计 JSON 快照"""
        path = self._ckpt_file(thread_id)
        writes_for_thread = {k: dict(v) for k, v in self.writes.items() if k[0] == thread_id}
        blobs_for_thread = {k: v for k, v in self.blobs.items() if k[0] == thread_id}
        storage_for_thread = {k: dict(v) for k, v in self.storage.get(thread_id, {}).items()}
        try:
            with open(path, "wb") as f:
                pickle.dump({
                    "storage": storage_for_thread,
                    "writes": writes_for_thread,
                    "blobs": blobs_for_thread
                }, f)
        except Exception:
            pass

        # 同步写入一份易于人工审计排错的 JSON 镜像快照
        if checkpoint and "channel_values" in checkpoint:
            cv = checkpoint["channel_values"]
            for v in cv.values():
                if hasattr(v, "to_dict"):
                    json_path = self._json_file(thread_id)
                    try:
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(v.to_dict(), f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    break

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self._load_thread(thread_id)
        return super().get_tuple(config)

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        res = super().put(config, checkpoint, metadata, new_versions)
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self._save_thread(thread_id, checkpoint)
        return res

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        super().put_writes(config, writes, task_id, task_path)
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self._save_thread(thread_id)

    def delete_thread(self, thread_id: str):
        super().delete_thread(thread_id)
        for p in [self._ckpt_file(thread_id), self._json_file(thread_id)]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    # 向下兼容旧版接口
    def save_checkpoint(self, thread_id: str, state_dict: Dict[str, Any]):
        filepath = self._json_file(thread_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, ensure_ascii=False, indent=2)

    def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        filepath = self._json_file(thread_id)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_checkpoint(self, thread_id: str):
        self.delete_thread(thread_id)


class LocalCheckpointer(LangGraphFileCheckpointer):
    """向下兼容别名类，保持老代码与单元测试无缝衔接"""
    pass
