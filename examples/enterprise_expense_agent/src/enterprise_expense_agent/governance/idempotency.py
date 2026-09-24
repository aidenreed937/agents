"""Layer 5: 业务治理与合规层 - 接口幂等性治理引擎 (Idempotency Manager)
防止在网络超时重试、用户连击、模型多轮幻觉调用时，重复向财务系统创建报销单、重复打款或重复记账。
"""
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

class IdempotencyStatus(str, Enum):
    PENDING = "PENDING"        # 处理中，类似执行期排他锁
    COMPLETED = "COMPLETED"    # 已成功完成，缓存最终交付结果
    FAILED = "FAILED"          # 执行失败，可允许重试

@dataclass
class IdempotencyRecord:
    key: str
    status: IdempotencyStatus
    created_at: float
    result: Optional[Any] = None
    error_msg: Optional[str] = None

class IdempotencyManager:
    """企业级接口幂等控制中心"""

    def __init__(self, ttl_seconds: float = 3600.0):
        self.ttl = ttl_seconds
        self._records: Dict[str, IdempotencyRecord] = {}

    @staticmethod
    def generate_key_from_version_hash(user_id: str, version_hash: str) -> str:
        """
        基于用户 ID 与 ValidatedExpenseClaim 的版本哈希生成强业务幂等键
        """
        raw = f"{user_id}::{version_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_key(user_id: str, invoice_code: str, category: str, amount: float) -> str:
        """
        基于关键业务唯一指纹生成确定性 SHA-256 幂等哈希键
        """
        raw_fingerprint = f"{user_id}::{invoice_code.strip().upper()}::{category.strip()}::{amount:.2f}"
        return hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()

    def get_record(self, key: str) -> Optional[IdempotencyRecord]:
        """获取当前记录状态（用于恢复期或探查）"""
        return self._records.get(key)


    def check_or_lock(self, key: str) -> Tuple[bool, Optional[Any]]:
        """
        检查幂等键状态
        返回: (是否允许执行新的业务操作, 已有的历史结果)
        - 若返回 (True, None): 表示获取锁成功，可以继续调用外部 API 创建单据
        - 若返回 (False, result): 表示该操作之前已成功完成，直接返回历史单据，严禁二次调用外部 API
        - 若处于 PENDING: 抛出并发调用异常
        """
        now = time.time()
        record = self._records.get(key)

        if record:
            # 检查是否过期
            if now - record.created_at > self.ttl:
                del self._records[key]
            else:
                if record.status == IdempotencyStatus.COMPLETED:
                    # 幂等命中，直接返回已有单据，不重复写入
                    return False, record.result
                elif record.status == IdempotencyStatus.PENDING:
                    raise RuntimeError(f"幂等冲突：该业务单据请求正在并发处理中 (Key: {key[:8]}...)，请勿重复提交")
                elif record.status == IdempotencyStatus.FAILED:
                    # 失败允许重试，重置为 PENDING
                    record.status = IdempotencyStatus.PENDING
                    record.created_at = now
                    return True, None

        # 首次调用，记录 PENDING 状态
        self._records[key] = IdempotencyRecord(
            key=key,
            status=IdempotencyStatus.PENDING,
            created_at=now,
        )
        return True, None

    def mark_completed(self, key: str, result: Any) -> None:
        """业务操作成功，固化幂等执行结果"""
        if key in self._records:
            record = self._records[key]
            record.status = IdempotencyStatus.COMPLETED
            record.result = result

    def mark_failed(self, key: str, error_msg: str) -> None:
        """业务操作异常，释放或标记失败状态以便后续安全重试"""
        if key in self._records:
            record = self._records[key]
            record.status = IdempotencyStatus.FAILED
            record.error_msg = error_msg

    def rollback(self, key: str) -> None:
        """撤销幂等锁"""
        if key in self._records:
            del self._records[key]
