# 02-web-fullstack / Web 全栈工程

## 模块目标
梳理现代 Web 前端与前后端协作工程能力，聚焦 React、TypeScript、流式通信（SSE）与前后端鉴权体系。

## 重点课题
1. **TypeScript 类型系统**
   - 常用高级类型与泛型设计（Utility Types、Conditional Types、Infer）
   - 类型守卫（Type Guards）与严格模式下的类型收窄
   - 前后端接口契约的类型安全对齐（API Schema 映射）
2. **React 核心原理与模式**
   - 组件生命周期、Hooks 原理与闭包陷阱
   - 渲染性能优化策略（memo、useMemo、useCallback、虚拟滚动）
   - 状态管理选型与适用场景（Zustand、Context API、TanStack Query）
3. **Web 协议与长连接交互**
   - HTTP/1.1、HTTP/2、HTTP/3 差异
   - Server-Sent Events (SSE) 协议原理与断线自动重连机制
   - 跨域资源共享（CORS）预检流程与排障
4. **认证与授权**
   - JWT vs Session / Cookie 适用场景与安全取舍（XSS、CSRF 防御）
   - 基于 RBAC 的权限拦截设计（前端路由守卫与后端接口鉴权）
