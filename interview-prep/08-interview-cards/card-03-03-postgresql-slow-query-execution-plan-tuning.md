# 面试卡：PostgreSQL 慢查询定位与 Explain Analyze 执行计划调优

**模块**：03-database-system ｜ **难度**：高级 ｜ **熟练度**：A

---

### 1. 30 秒电梯回答
慢查询治理遵循**“慢日志定位 → Explain Analyze 剖析代价 → 索引/参数调优 → 治理死元组与表膨胀”**。
- **定位与剖析**：开启 `pg_stat_statements` 抓取瓶颈 SQL，执行 `EXPLAIN (ANALYZE, BUFFERS)` 重点核查全表扫描（Seq Scan）、索引失效及行数预估漂移（Rows vs Actual Rows）；
- **瓶颈根治**：针对 Hash Join/Nested Loop 不当建立联合或覆盖索引（Index Only Scan）；调大 `work_mem` 根治磁盘排序溢出（external merge Disk），定期 VACUUM 治理表膨胀。

---

### 2. 深入原理
1. **Explain Analyze 核心指标深度解析**：
   - `Cost`：优化器预估代价（启动代价..总代价）。
   - `Actual Time`：真实执行耗时（首次返回毫秒..全部完成毫秒）。
   - `Rows` vs `Actual Rows`：预估行数与真实行数对比。若两者相差数个数量级，说明表的统计信息陈旧，优化器生成了错误的执行计划，需执行 `ANALYZE tablename;` 刷新统计信息。
   - `Buffers: shared hit=... read=...`：`hit` 是命中内存缓冲池，`read` 是发生物理磁盘读取。`read` 越高说明 I/O 瓶颈越大。
2. **扫描节点类型与选择机制**：
   - **Seq Scan**：全表顺序扫描。通常在缺乏索引、或过滤条件选择率极低（比如查询结果占全表 50% 以上）时由优化器主动选用。
   - **Index Scan**：走索引查找堆表物理行。适合返回少量数据（高选择性）。
   - **Index Only Scan**：覆盖索引扫描。所需字段全部在索引树中（需结合 VM 可见性映射图），无需回表，性能最高。
   - **Bitmap Index Scan + Bitmap Heap Scan**：先利用索引构建位图再批量回表读取，适合结果集在物理块上分布较散但总体数据量中等的场景。
3. **内存溢出与工作内存（work_mem）**：
   - `Sort Method: external merge Disk: 4096kB`：说明排序内存超过了 `work_mem` 上限，触发了昂贵的磁盘临时文件排序。应针对特定复杂查询局部调大 `SET work_mem = '64MB';`。

---

### 3. 工程取舍与边界
- **索引不是越多越好**：PostgreSQL 采用 MVCC 追加写模型，每次 `UPDATE` 都会生成新版本行（行指针变化）。如果表上建了 10 个索引，一次更新必须同步修改这 10 个索引树，导致严重的写放大（Write Amplification）。只有能够利用 HOT（Heap-Only Tuples）特性的单字段更新才能避免索引重写。

---

### 4. 高频追问应对
- **追问 1：为什么字段明明建立了 B-Tree 索引，Explain 依然走了 Seq Scan？**
  - **应对**：常见四大原因：
    1. **选择率过低**：优化器判定返回数据占比超过 15%~20%，认为走索引随机 I/O 的代价高于全表顺序 I/O；
    2. **对索引列进行了函数计算或类型隐式转换**（如 `WHERE LOWER(email) = ...` 或字符与数值隐式强转），导致索引失效；
    3. **不符合最左匹配原则**（在复合索引中跳过了前导列）；
    4. **表数据量极小**：全表只有几百行，顺序读取几个数据块比先读索引再读堆表更快。
- **追问 2：PostgreSQL 中经常出现查询越来越慢，重建索引后立即恢复，根因是什么？**
  - **应对**：这是典型的 **表与索引膨胀（Bloat）**。频繁的 UPDATE/DELETE 会产生大量 Dead Tuples，若 `autovacuum` 参数过于保守未能及时清理空间，导致数据块稀疏，B-Tree 索引树层级异常膨胀。应对手段：调优 autovacuum 阈值（如减小 `autovacuum_vacuum_scale_factor`），必要时使用 `pg_repack` 在线无锁整理表与索引。
- **追问 3：在分页查询 `LIMIT 10 OFFSET 100000` 极慢时，如何优化？**
  - **应对**：`OFFSET` 会从磁盘真实扫描并丢弃前 10 万行数据。优化方案：
    1. **游标/寻址分页（Keyset Pagination）**：`WHERE id > last_seen_id ORDER BY id ASC LIMIT 10`，直接走索引定位起点，耗时为恒定 $O(\log N)$；
    2. **延迟关联（Deferred Join）**：先通过子查询走覆盖索引拿到主键 ID，再回表关联出完整字段。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿说明 `Rows` 与 `Actual Rows` 偏差极大时的诊断与修复动作？
- [ ] 能否讲清 Index Scan、Index Only Scan 与 Bitmap Heap Scan 的适用差异？
- [ ] 能否说出深度分页 `OFFSET` 慢查询的两种工业级优化解法？
