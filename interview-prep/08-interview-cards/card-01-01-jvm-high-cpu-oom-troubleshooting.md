# 面试卡：生产环境 CPU 100% 与 OOM 排障全链路

**模块**：01-java-backend ｜ **难度**：高级 ｜ **熟练度**：A

---

### 1. 30 秒电梯回答
生产排障遵循**“先止血、再保留现场、后离线根因分析”**的原则。
- 对于 **CPU 100%**：使用 `top -Hp` 定位消耗 CPU 最高的具体线程 TID，转换为十六进制后通过 `jstack` 抓取线程堆栈，精准定位是死循环、JIT 编译风暴、还是 Full GC 频繁引起的停顿。
- 对于 **OOM**：JVM 必须预置 `-XX:+HeapDumpOnOutOfMemoryError` 自动生成 dump 文件；通过 `jstat -gcutil` 观察各分代增长趋势，结合 MAT（Memory Analyzer Tool）或 JProfiler 分析支配树（Dominator Tree），找出持有大量内存的根对象链（GC Roots）。

---

### 2. 深入原理
1. **CPU 飙高的典型排查链路（4 步法）**：
   - 第一步：`top` 找到 CPU 占用率极高的 Java 进程 PID。
   - 第二步：`top -Hp <PID>` 找出该进程内占用 CPU 最多的具体线程 LWP/TID（十进制）。
   - 第三步：`printf "%x\n" <TID>` 将十进制线程 ID 转为十六进制 `nid`。
   - 第四步：`jstack <PID> | grep -A 30 "0x<nid>"` 定位该线程当前正在执行的代码行或 GC 工作线程（如 `VM Thread` / `Gang worker`）。
2. **OOM 场景分类与根因定位**：
   - **`Java heap space`**：堆内存不足。原因多为大对象未释放、长生命周期集合类持续泄漏、单次 SQL 查询未分页拉取全量数据。排查重点是检查支配树中的单体大对象与 Retained Size。
   - **`Metaspace`**：元空间不足。多由于动态生成大量代理类（CGLIB、反射、动态脚本）且未被垃圾回收，或类加载器（ClassLoader）泄漏。
   - **`unable to create new native thread`**：操作系统线程句柄耗尽。多由于应用未复用线程池，而是不断 `new Thread()`，或操作系统 `max user processes`（`ulimit -u`）限制过紧。

---

### 3. 工程取舍与边界
- **保留现场 vs 恢复业务**：在线上多节点集群中，第一时间将故障节点的流量从网关摘除（下线），保留该节点抓取 `jstack`、`jmap -histo:live` 或内存 dump 后再重启服务，严禁直接全量重启而丢失案发现场证据。
- **线上执行 `jmap -dump` 的风险**：在大内存（>16GB）生产节点上执行 `jmap -dump:live` 会触发全局 STW（Stop-The-World），导致服务瞬时假死。首选依赖 JVM 预置的 OOM 自动 Dump 参数，或借助 Arthas 等非侵入式热诊断工具。

---

### 4. 高频追问应对
- **追问 1：如果 `jstack` 发现高 CPU 的线程全是 `VM Thread` 或 `GC task thread`，说明了什么？**
  - **应对**：说明 CPU 飙高的根因不是业务代码死循环，而是**内存耗尽触发了持续不断的 Full GC**。GC 线程在拼命扫描可回收对象但回收无效，占满了所有 CPU 核心。此时应立刻转向分析内存使用率和堆 Dump，而不是检查业务代码中的循环逻辑。
- **追问 2：为什么有时堆内存看起来并不大，但物理内存被 Java 进程吃光并被 Linux OOM Killer 杀掉？**
  - **应对**：这是**堆外内存（Off-Heap）泄漏**。常见于 Netty DirectByteBuffer 未释放、JNI 本地代码内存泄漏、或者 JVM 内部元空间/代码缓存增长。可以通过开启 Native Memory Tracking（`-XX:NativeMemoryTracking=detail`）配合 `jcmd <PID> VM.native_memory detail` 排查堆外占用。
- **追问 3：在容器化环境（Docker / K8s）中跑 Java，有哪些特殊的 JVM 参数配置？**
  - **应对**：低版本 JDK（<8u191）无法感知 Cgroups 资源限制，会将宿主机整体 CPU/内存当成可用上限，导致容器因超过 Limit 被 OOMKilled。必须使用支持容器感知的 JDK 版本，并配置 `-XX:+UseContainerSupport`、`-XX:MaxRAMPercentage=75.0`，为堆外和系统进程预留 25% 缓冲空间。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿默写出 `top -> top -Hp -> printf "%x" -> jstack` 串联定位的命令链？
- [ ] 能否讲清 GC 线程引起 CPU 飙高的传导因果逻辑？
- [ ] 能否说出容器环境下 JVM 内存超额被 Kill 的原因及解决方案（MaxRAMPercentage）？
