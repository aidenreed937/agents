# 面试卡：Spring 声明式事务失效根因与分布式业务幂等设计

**模块**：01-java-backend ｜ **难度**：高级 ｜ **熟练度**：A

---

### 1. 30 秒电梯回答
企业级事务与幂等设计的核心是**“理解 AOP 代理边界，构筑数据库唯一约束兜底”**。
- **事务失效根因**：Spring `@Transactional` 基于 **AOP 动态代理**实现。类内部自调用（`this.method()`）绕过代理导致失效；非 public 方法、异步跨线程调用、吞异常或未指定 `rollbackFor` 均会导致事务无法正常回滚；
- **业务幂等设计**：防重核心依赖**“唯一业务键 + 防重状态机 + 数据库唯一约束”**。前端或客户端生成全局 `idempotency_key` 配合 Redis 防重令牌，核心落库阶段由数据库唯一联合索引提供最终 ACID 兜底。

---

### 2. 深入原理
1. **Spring AOP 代理与事务拦截机制**：
   - Spring 容器启动时，若目标类实现接口则默认使用 JDK 动态代理，未实现接口则使用 CGLIB 生成子类代理。
   - 外部调用进入代理对象的 `invoke()`，触发 `TransactionInterceptor` 执行 `PlatformTransactionManager.getTransaction()` 开启事务，执行目标逻辑后根据异常决定 `commit()` 或 `rollback()`。
   - **类自调用失效解法**：
     - 注入自身代理对象（`@Autowired private MyService selfService;`）；
     - 使用 `AopContext.currentProxy()`（需开启 `exposeProxy=true`）；
     - 将事务方法抽离至独立的 Service 组件中（推荐最佳实践）。
2. **事务传播机制（Propagation）核心场景**：
   - `REQUIRED`（默认）：有事务则加入，无事务则新建。适合绝大多数业务聚合。
   - `REQUIRES_NEW`：无论当前有无事务，均新建独立事务挂起原事务。**典型应用**：业务失败回滚，但操作审计日志（Audit Log）必须强制落盘提交。
   - `NESTED`：保存点（Savepoint）嵌套事务。子事务回滚仅回滚至保存点，不影响外部事务提交；外部事务回滚则子事务全部回滚。

---

### 3. 工程取舍与边界
- **长事务风险（Long Transaction）**：严禁在 `@Transactional` 方法内执行耗时外部网络调用（如调用外部第三方 HTTP API、等待 LLM 生成或执行大型邮件发送）。长事务会长期霸占数据库连接池连接，并持有行锁/间隙锁，极易引发连接池耗尽与死锁。必须将“外部网络调用”与“本地数据库事务”严格拆分。

---

### 4. 高频追问应对
- **追问 1：如果方法抛出了受检异常（Checked Exception 如 `IOException`），Spring 会回滚吗？**
  - **应对**：默认**不会回滚**。Spring 规范默认仅在遇到未捕获的 `RuntimeException` 和 `Error` 时触发回滚。若需要针对受检异常回滚，必须显式声明 `@Transactional(rollbackFor = Exception.class)`。
- **追问 2：在高并发创建订单或扣款场景下，仅靠数据库唯一索引防重够不够？**
  - **应对**：不够。仅靠唯一索引虽然能保证最终一致性，但在极端高并发瞬时重试下，大量重复请求打入数据库会造成大量唯一键冲突异常（`DuplicateKeyException`），引发频繁行锁等待甚至死锁。生产级方案必须是**“前端防抖 + Redis 分布式锁瞬时前置拦截 + 数据库唯一索引兜底”**三道防线。
- **追问 3：在声明式事务中，如果想在事务提交成功之后再发送消息队列（MQ）通知下游，怎么保证？**
  - **应对**：不能直接写在方法末尾（此时数据库事务尚未真正提交，若 MQ 发送成功但随后的事务提交发生网络超时或约束冲突失败，会导致下游消费了脏数据）。必须使用 Spring 提供的 `TransactionSynchronizationManager.registerSynchronization`，或者监听事务成功事件：`@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)`。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿讲清 AOP 代理机制如何导致类内部自调用事务失效？
- [ ] 能否区分 `REQUIRES_NEW` 与 `NESTED` 在独立回滚场景下的底层实现差异？
- [ ] 能否阐述为什么长事务中绝对不能包含外部大模型/网络 API 调用？
