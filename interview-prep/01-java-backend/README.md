# 01-java-backend / Java 后端工程

## 模块目标
复用已有 Java 经验，查漏补缺，重点强化生产环境高频深挖点：并发模型、JVM 内部机制与排障、Spring 核心机制与事务传播。

## 重点课题
1. **Java 并发与多线程**
   - JMM、volatile 原理与内存屏障
   - 线程池参数设计、拒绝策略与动态调优
   - AQS 核心原理与常用锁（ReentrantLock、StampedLock）
   - 并发容器（ConcurrentHashMap 扩容与加锁演进）
2. **JVM 调优与排障**
   - 内存区域划分与对象生命周期
   - 垃圾回收器对比（G1、ZGC）核心特征与停顿控制
   - 常见故障排查方法（OOM、CPU 100%、死锁，对应工具与实操链路）
3. **Spring Boot 与企业级开发**
   - IoC 容器生命周期、循环依赖解决策略与限制
   - Spring 声明式事务原理（AOP 代理机制、事务传播行为、事务失效场景）
   - 过滤器（Filter）与拦截器（Interceptor）生命周期与适用边界
