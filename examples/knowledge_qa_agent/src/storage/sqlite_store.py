"""本地持久化引擎 (基于 SQLite + FTS5 原生全文倒排索引)
无需安装任何外部重型数据库，单文件磁盘持久化，支持：
1. 元数据与父子切片关系持久化 (ACID 事务)
2. 原生 FTS5 倒排索引与 BM25 全文检索
3. 向量二进制序列化存储与冷启动快速恢复
"""
import sqlite3
import json
import struct
from typing import List, Optional, Tuple, Dict, Any
from ..models import Chunk, ActionLink, SearchResult, UserContext
from ..retrieval.bm25 import BM25Retriever


class SQLiteLocalStore:
    """基于 SQLite 的嵌入式本地持久化存储器"""

    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_db(self):
        """初始化关系表与 FTS5 虚拟全文检索表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL;")

            # 1. 基础切片元数据表 (支持多租户与 RBAC 权限硬隔离)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT,
                title TEXT,
                breadcrumbs_json TEXT,
                raw_content TEXT,
                contextual_prefix TEXT,
                parent_id TEXT,
                is_parent INTEGER,
                console_path TEXT,
                cli_command TEXT,
                required_permission TEXT,
                tenant_id TEXT DEFAULT 'public',
                embedding_blob BLOB,
                metadata_json TEXT
            );
            """)

            # 兼容历史已存在的表，补充 tenant_id 字段
            cursor.execute("PRAGMA table_info(chunks);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "tenant_id" not in columns:
                cursor.execute("ALTER TABLE chunks ADD COLUMN tenant_id TEXT DEFAULT 'public';")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tenant_perm ON chunks(tenant_id, required_permission);")

            # 2. SQLite 原生 FTS5 全文倒排索引表（自带 BM25 算法支持）
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                title,
                contextualized_text,
                tokenize = 'porter unicode61'
            );
            """)
            conn.commit()

    def save_chunks(self, chunks: List[Chunk], embeddings_map: Optional[Dict[str, List[float]]] = None):
        """批量持久化切片与向量到本地磁盘数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for c in chunks:
                emb_blob = None
                if embeddings_map and c.chunk_id in embeddings_map:
                    emb = embeddings_map[c.chunk_id]
                    emb_blob = struct.pack(f"{len(emb)}f", *emb)

                action = c.action_link
                c_path = action.console_path if action else None
                cli_cmd = action.cli_command if action else None
                perm = c.required_permission
                tenant = c.tenant_id or "public"

                cursor.execute("""
                INSERT OR REPLACE INTO chunks (
                    chunk_id, doc_id, title, breadcrumbs_json, raw_content,
                    contextual_prefix, parent_id, is_parent, console_path,
                    cli_command, required_permission, tenant_id, embedding_blob, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.chunk_id,
                    c.doc_id,
                    c.title,
                    json.dumps(c.breadcrumbs, ensure_ascii=False),
                    c.raw_content,
                    c.contextual_prefix,
                    c.parent_id,
                    1 if c.is_parent else 0,
                    c_path,
                    cli_cmd,
                    perm,
                    tenant,
                    emb_blob,
                    json.dumps(c.metadata, ensure_ascii=False)
                ))

                # 同步更新 FTS5 倒排索引 (中英文分词与 2-gram 优化)
                fts_tokens = " ".join(BM25Retriever.tokenize(f"{c.title} {c.contextualized_content}"))
                cursor.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c.chunk_id,))
                cursor.execute("""
                INSERT INTO chunks_fts (chunk_id, title, contextualized_text)
                VALUES (?, ?, ?)
                """, (c.chunk_id, c.title, fts_tokens))

            conn.commit()

    def delete_document(self, doc_id: str) -> int:
        """删除指定文档的所有切片及其全文索引"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc_id,))
            chunk_ids = [row["chunk_id"] for row in cursor.fetchall()]
            if not chunk_ids:
                return 0
            cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            for cid in chunk_ids:
                cursor.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,))
            conn.commit()
            return len(chunk_ids)

    def load_all_chunks(self, user_context: Optional[UserContext] = None) -> Tuple[List[Chunk], List[Chunk], Dict[str, List[float]]]:
        """从本地磁盘数据库冷启动加载所有父块、子块和向量 (支持多租户与 RBAC 前置过滤)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_context and user_context.tenant_id != "public":
                cursor.execute("SELECT * FROM chunks WHERE tenant_id = ? OR tenant_id = 'public'", (user_context.tenant_id,))
            else:
                cursor.execute("SELECT * FROM chunks")
            rows = cursor.fetchall()

            parents: List[Chunk] = []
            children: List[Chunk] = []
            embeddings_map: Dict[str, List[float]] = {}

            for r in rows:
                action = None
                if r["console_path"]:
                    action = ActionLink(
                        console_path=r["console_path"],
                        cli_command=r["cli_command"],
                        required_permission=r["required_permission"]
                    )

                tenant = r["tenant_id"] if "tenant_id" in r.keys() and r["tenant_id"] else "public"

                chunk = Chunk(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    title=r["title"],
                    breadcrumbs=json.loads(r["breadcrumbs_json"]),
                    raw_content=r["raw_content"],
                    contextual_prefix=r["contextual_prefix"] or "",
                    parent_id=r["parent_id"],
                    is_parent=bool(r["is_parent"]),
                    action_link=action,
                    tenant_id=tenant,
                    metadata=json.loads(r["metadata_json"] or "{}")
                )

                # RBAC 细粒度权限过滤
                if user_context and not user_context.has_permission(chunk.required_permission):
                    continue

                if chunk.is_parent:
                    parents.append(chunk)
                else:
                    children.append(chunk)
                    if r["embedding_blob"]:
                        # 反序列化 Float32 向量
                        blob = r["embedding_blob"]
                        num_floats = len(blob) // 4
                        vec = list(struct.unpack(f"{num_floats}f", blob))
                        embeddings_map[chunk.chunk_id] = vec

            return parents, children, embeddings_map

    def fts5_search(self, query: str, top_k: int = 5, user_context: Optional[UserContext] = None) -> List[SearchResult]:
        """利用 SQLite 原生 FTS5 引擎在磁盘上执行 BM25 检索 (具备多租户与 RBAC 物理硬隔离)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            tokens = [t for t in BM25Retriever.tokenize(query) if len(t) > 1]
            safe_query = " OR ".join(tokens) if tokens else f'"{query}"'
            fetch_limit = top_k * 3 if user_context else top_k

            try:
                if user_context and user_context.tenant_id != "public":
                    sql = """
                    SELECT c.*, bm25(chunks_fts) as bm25_score
                    FROM chunks_fts f
                    JOIN chunks c ON f.chunk_id = c.chunk_id
                    WHERE chunks_fts MATCH ?
                      AND (c.tenant_id = ? OR c.tenant_id = 'public')
                    ORDER BY bm25_score ASC
                    LIMIT ?
                    """
                    cursor.execute(sql, (safe_query, user_context.tenant_id, fetch_limit))
                else:
                    sql = """
                    SELECT c.*, bm25(chunks_fts) as bm25_score
                    FROM chunks_fts f
                    JOIN chunks c ON f.chunk_id = c.chunk_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY bm25_score ASC
                    LIMIT ?
                    """
                    cursor.execute(sql, (safe_query, fetch_limit))
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # 若包含特殊字符语法错误，降级为普通扫描
                if user_context and user_context.tenant_id != "public":
                    cursor.execute(
                        "SELECT c.*, 1.0 as bm25_score FROM chunks c WHERE c.tenant_id = ? OR c.tenant_id = 'public' LIMIT ?",
                        (user_context.tenant_id, fetch_limit)
                    )
                else:
                    cursor.execute("SELECT c.*, 1.0 as bm25_score FROM chunks c LIMIT ?", (fetch_limit,))
                rows = cursor.fetchall()

            results = []
            for r in rows:
                action = None
                if r["console_path"]:
                    action = ActionLink(
                        console_path=r["console_path"],
                        cli_command=r["cli_command"],
                        required_permission=r["required_permission"]
                    )
                tenant = r["tenant_id"] if "tenant_id" in r.keys() and r["tenant_id"] else "public"

                chunk = Chunk(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    title=r["title"],
                    breadcrumbs=json.loads(r["breadcrumbs_json"]),
                    raw_content=r["raw_content"],
                    contextual_prefix=r["contextual_prefix"] or "",
                    parent_id=r["parent_id"],
                    is_parent=bool(r["is_parent"]),
                    action_link=action,
                    tenant_id=tenant,
                    metadata=json.loads(r["metadata_json"] or "{}")
                )

                # RBAC 权限过滤阻断
                if user_context and not user_context.has_permission(chunk.required_permission):
                    continue

                results.append(SearchResult(
                    chunk=chunk,
                    score=abs(round(r["bm25_score"], 4)),
                    rank=len(results) + 1,
                    source_type="sqlite_fts5"
                ))
                if len(results) >= top_k:
                    break

            return results
