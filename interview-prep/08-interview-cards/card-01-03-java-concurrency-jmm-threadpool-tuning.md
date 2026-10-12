# 面试卡：Java 内存模型（JMM）、volatile 底层屏障与线程池生产调优

**模块**：01-java-backend ｜ **难度**：高级 ｜ **熟练度**：A

---

### 1. 30 秒电梯回答
- **JMM 与 volatile**：Java 内存模型通过定义主内存（Main Memory）与工作内存（Working Memory）解决并发下的可见性、原子性与有序性问题。`volatile` 变量通过底层汇编指令（如 x86 的 `lock addl`）插入**内存屏障（Load/Store Barrier）**，禁止指令重排序，并强制刷新写缓冲区（Store Buffer）至主内存，使其他 CPU 核心的 L1/L2 缓存行失效（基于 MESI 缓存一致性协议），从而实现强可见性与有序性，但**不保证复合操作的原子性**。
- **线程池调优**：严禁使用 `Executors` 快捷工厂方法创建无界队列线程池。生产必须使用 `ThreadPoolExecutor`，区分 CPU 密集型与 I/O 密集型设计核心线程数，配置有界队列（`ArrayBlockingQueue`），并建立动态参数调节与拒绝策略监控。

---

### 2. 深入原理
1. **volatile 底层硬件实现**：
   - 编译器在编译 volatile 读写时插入四种内存屏障：`LoadLoad`, `LoadStore`, `StoreStore`, `StoreLoad`。
   - 在 x86 架构下，大部分读写是有序的，关键在于写操作后插入带有 `lock` 前缀的指令。该指令锁住缓存行/总线，强制将 Store Buffer 内容冲刷到主内存，并通过 CPU 总线嗅探机制（Bus Snooping）使所有其他核心缓存该变量的 Cache Line 置为 Invalid 状态。
2. **Happens-Before 规则核心**：
   - 程序次序规则、管程锁定规则（解锁 happens-before 加锁）、volatile 变量规则（写 happens-before 后续读）、传递性规则。
3. **线程池运行机制与参数配置**：
   - **执行流程**：核心线程数（`corePoolSize`）→ 阻塞队列（`workQueue`）→ 最大线程数（`maximumPoolSize`）→ 拒绝策略（`handler`）。
   - **经验参数设计**：
     - CPU 密集型：$N_{threads} = N_{cpu} + 1$（额外 1 个线程防页缺失或中断）。
     - I/O 密集型（如涉及频繁网络调用、LLM 调用、DB 读写）：$N_{threads} = N_{cpu} \times \left(1 + \frac{\text{等待时间}}{\text{计算时间}}\right)$，常见配置为 $2N_{cpu} \sim 4N_{cpu}$。
   - **有界队列容量**：队列过大导致请求堆积引发内存 OOM，且无法及时触发扩容到最大线程；队列过小容易触发拒绝策略。需结合系统 P99 耗时与突发请求量计算。

---

### 3. 工程取舍与边界
- **CallerRunsPolicy 的双刃剑**：生产中最常用的拒绝策略是 `CallerRunsPolicy`（让提交任务的调用方线程自己执行该任务）。这能在高并发打满时产生**天然的背压（Backpressure）机制**，让调用方暂停提交新任务；但代价是如果调用方是 Netty IO 线程或 Web 容器分发线程，调用方被长时间阻塞可能导致整个网络监听接口假死。

---

### 4. 高频追问应对
- **追问 1：为什么单例模式的双重检查锁定（DCL）中，静态变量必须加 `volatile`？**
  - **应对**：`new Singleton()` 实际上由三条指令组成：1. 分配内存空间；2. 初始化对象构造函数；3. 将引用指向该内存空间。若没有 `volatile`，JVM 可能发生指令重排序（1 → 3 → 2）。线程 A 执行完 3 尚未执行 2 时，线程 B 判断 `instance != null` 直接返回了一个**半初始化（Half-initialized）的脏对象**，引发空指针或严重逻辑异常。
- **追问 2：生产线上如何实现线程池参数（corePoolSize、maxPoolSize）的热修改且不重启服务？**
  - **应对**：使用 `ThreadPoolExecutor` 提供的原生 API：`setCorePoolSize()`、`setMaximumPoolSize()`。结合 Nacos/Apollo 等配置中心监听配置变更；但需注意：如果动态调小 corePoolSize，还需显式开启 `allowCoreThreadTimeOut(true)` 允许核心线程空闲超时回收；若要修改阻塞队列容量，需自定义可动态变更容量的 `ResizableCapacityLinkedBlockingQueue`。
- **追问 3：线程池中如果某个任务执行时抛出了未捕获的 RuntimeException，该线程会销毁吗？**
  - **应对**：使用 `execute()` 提交时，未捕获异常会导致工作线程异常终止退出，JVM 会销毁该线程并重新创建一个新工作线程加入线程池；如果使用 `submit()` 提交，异常会被封装在返回的 `FutureTask` 中，线程不会退出，若调用方未显式调用 `Future.get()`，该异常会被静默吞噬。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿画出 DCL 指令重排序导致半初始化对象的时序图？
- [ ] 能否讲清 volatile 在底层 x86 架构上的 lock 汇编指令与 MESI 缓存失效过程？
- [ ] 能否说明 execute 与 submit 提交任务时对未捕获异常处理的底层差异？
