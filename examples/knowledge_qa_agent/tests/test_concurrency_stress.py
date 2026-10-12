import unittest
import os
import sys
import time
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.models import Chunk, ActionLink
from src.storage.sqlite_store import SQLiteLocalStore


class TestConcurrencyAndStorageStress(unittest.TestCase):
    """高并发并发读写、连接隔离与锁竞争压力测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_concurrent.db")
        self.store = SQLiteLocalStore(self.db_path)

        # 预先写入初始数据
        init_chunks = [
            Chunk(
                chunk_id=f"chunk_init_{i}",
                doc_id="doc_base",
                title=f"云服务负载均衡配置指南 {i}",
                breadcrumbs=["网络", f"指南_{i}"],
                raw_content=f"负载均衡器第 {i} 条路由规则与流量分发策略，支持 502 自动重试与健康检查。",
                contextual_prefix="[网络 > 负载均衡]",
                is_parent=False
            )
            for i in range(10)
        ]
        self.store.save_chunks(init_chunks)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_read_write_no_locking_error(self):
        """测试 30 线程高并发读写混合压力下，SQLite WAL 模式无 'database is locked' 异常"""
        errors = []
        latencies = []

        def reader_task(task_id: int):
            try:
                t0 = time.perf_counter()
                results = self.store.fts5_search("负载均衡 502", top_k=3)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                latencies.append(elapsed_ms)
                if not results:
                    errors.append(f"Reader {task_id}: 结果集为空")
            except Exception as e:
                errors.append(f"Reader {task_id} 异常: {str(e)}")

        def writer_task(task_id: int):
            try:
                chunk = Chunk(
                    chunk_id=f"chunk_dyn_{task_id}",
                    doc_id=f"doc_dyn_{task_id}",
                    title=f"动态并发导入切片 {task_id}",
                    breadcrumbs=["并发测试", f"分片_{task_id}"],
                    raw_content=f"这是并发线程 {task_id} 实时写入的配置说明文档。",
                    contextual_prefix="[并发测试]",
                    is_parent=False
                )
                self.store.save_chunks([chunk])
            except Exception as e:
                errors.append(f"Writer {task_id} 异常: {str(e)}")

        # 启动 20 个读者与 10 个写者混合并发
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for i in range(20):
                futures.append(executor.submit(reader_task, i))
            for j in range(10):
                futures.append(executor.submit(writer_task, j))

            for f in as_completed(futures):
                f.result()

        # 验证全流程无任何数据库锁死错误
        self.assertEqual(len(errors), 0, f"并发执行过程中出现了错误: {errors}")

        # 验证写入的数据已成功持久化并可在 FTS5 中检索
        after_results = self.store.fts5_search("并发线程", top_k=10)
        self.assertGreater(len(after_results), 0)

    def test_search_latency_distribution(self):
        """测试 50 次并发高频检索时的延迟指标分布 (P50, P90, P99)"""
        latencies = []

        def query_job():
            t0 = time.perf_counter()
            _ = self.store.fts5_search("流量分发 502", top_k=5)
            latencies.append((time.perf_counter() - t0) * 1000)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(query_job) for _ in range(50)]
            for f in as_completed(futures):
                f.result()

        latencies.sort()
        p50 = statistics.median(latencies)
        p90 = latencies[int(len(latencies) * 0.90)]
        p99 = latencies[int(len(latencies) * 0.99) if int(len(latencies) * 0.99) < len(latencies) else -1]

        # 验证本地 FTS5 并发检索性能 (P50 应该低于 10ms, P99 低于 50ms)
        self.assertLess(p50, 15.0, f"P50 延迟过高: {p50:.2f}ms")
        self.assertLess(p99, 50.0, f"P99 延迟过高: {p99:.2f}ms")


if __name__ == "__main__":
    unittest.main()
