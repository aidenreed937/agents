# 面试卡：现代 Web 认证：双令牌无感刷新、跨端安全与 RBAC 权限设计

**模块**：02-web-fullstack ｜ **难度**：高级 ｜ **熟练度**：B

---

### 1. 30 秒电梯回答
生产级认证架构应兼顾**无状态横向扩展、短生命周期安全与用户无感续期**。
采用 **Access Token（短时效，如 15 分钟）+ Refresh Token（长时效，如 7~14 天）双令牌机制**。
- **Web 端安全存储**：Access Token 存内存（内存变量/状态管理），Refresh Token 存入带有 `HttpOnly`、`Secure`、`SameSite=Strict` 的 Cookie 中防范 XSS 窃取；
- **无感刷新（Silent Refresh）**：前端通过 Axios/Fetch 响应拦截器统一捕获 401，暂停挂起并发请求队列，利用互斥锁发起一次刷新请求，换取新 Token 后重放原请求队列；
- **权限设计**：结合 RBAC 模式，Access Token Payload 携带用户基本身份与角色，接口端通过网关/拦截器快速鉴权，高敏感接口二次校验数据库权限版本。

---

### 2. 深入原理
1. **双令牌轮转（Refresh Token Rotation, RTR）与防重放机制**：
   - 如果 Refresh Token 被黑客窃取，单纯依靠过期时间依然有长达数天的风险。
   - **RTR 轮转机制**：每次使用 Refresh Token 换取新 Access Token 时，服务端同时**废弃旧 Refresh Token，签发一个全新的 Refresh Token**。
   - **重放攻击检测（Replay Detection）**：若服务端检测到一个已经被废弃的旧 Refresh Token 再次被提交，立即判定该用户的 Token 族已被泄露，立刻**撤销（Revoke）该用户名下的所有活跃 Session**，强制要求重新密码登录。
2. **前端拦截器并发队列管理（Axios Interceptor Pattern）**：
   - 当页面同时发起 5 个并行 API 请求，且 Access Token 恰好过期时，避免 5 个请求同时调用 `/auth/refresh` 导致刷新冲突。
   - **方案**：维护一个 `isRefreshing` 互斥标志位与 `failedQueue = []`。第一个触发 401 的请求进入刷新流程，其余 4 个请求返回一个未决的 Promise 并将 `resolve/reject` 推入队列；刷新成功后逐一清空并重放队列，刷新失败则清空登录态跳转登录页。
3. **RBAC 权限模型与防越权校验**：
   - 角色-权限表设计：`User` ↔ `User_Role` ↔ `Role` ↔ `Role_Permission` ↔ `Permission`。
   - **垂直越权**（低权限访问高权限接口）：网关或注解层面校验角色权限码（如 `@PreAuthorize("hasAuthority('doc:write')")`）；
   - **水平越权**（访问同级别他人数据）：代码层强制注入当前登录用户的 `tenant_id` 与 `user_id`，SQL 查询条件必须强制包含 `WHERE owner_id = :currentUserId`，严禁信任客户端传入的主键参数。

---

### 3. 工程取舍与边界
- **无状态 JWT 的注销难题（Token Revocation）**：JWT 一旦签发，在有效期内任何持有者均可通过签名校验。如果管理员在后台封禁了某个违规用户，纯无状态 JWT 无法即时生效。折中方案：在 Redis 中维护一个只存违规用户 ID 或全局“密码修改时间戳”的黑名单/版本号；网关在校验 JWT 签名的同时，只去 Redis 查一次轻量版本号比对，兼顾性能与即时封禁。

---

### 4. 高频追问应对
- **追问 1：移动端（Android/iOS）与 Web 前端在存储 Token 时策略有何不同？**
  - **应对**：
    - **Web 端**：受限于浏览器沙箱与 XSS/CSRF 威胁，不能存 `localStorage`（极易被 XSS 读取），推荐短时 Token 存在内存、长时 Token 存 HttpOnly Cookie；
    - **移动端**：原生应用无跨站脚本（XSS）DOM 注入威胁，可以直接将 Token 安全保存在操作系统级安全存储区（如 Android 的 `EncryptedSharedPreferences` / Android Keystore，iOS 的 `Keychain`），并支持在 App 处于后台时自动保活与刷新。
- **追问 2：为什么不直接把所有权限明细都塞进 JWT Payload 里？**
  - **应对**：一是会导致 HTTP 标头急剧膨胀（每个请求都带几 KB 的 Header，浪费网络带宽）；二是用户权限变更（如被移除某项权限）时无法即时同步，必须等 Token 过期。Payload 只放最基础的 `userId`、`tenantId` 和极少数最高层级 `roles`，具体细粒度操作权限由服务端缓存（如 Redis）判定。
- **追问 3：在前后端分离架构中，CSRF 攻击是如何利用 Cookie 的？`SameSite=Lax/Strict` 是怎么防御的？**
  - **应对**：CSRF 是黑客通过钓鱼网站诱导浏览器自动向目标网站发送跨站请求，浏览器会自动携带该网站的 Cookie。配置 `SameSite=Strict` 会在所有跨站请求（无论链接点击还是 POST 提交）中绝对禁止携带该 Cookie；`SameSite=Lax` 仅允许顶层 GET 导航携带，从而切断了绝大多数跨站伪造请求的凭据传递。

---

### 5. 90 秒自测标准
- [ ] 能否脱稿讲清 Refresh Token 轮转（RTR）与重放攻击检测撤销的机制？
- [ ] 能否手写或讲清 Axios 响应拦截器通过 Promise 队列处理并发 401 刷新的逻辑？
- [ ] 能否说明水平越权与垂直越权在工程防线上的本质差异？
