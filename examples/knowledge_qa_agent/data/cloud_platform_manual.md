---
title: "云原生网络与安全网关操作手册"
version: "v2026.3"
category: "Network & Security"
---

<!-- 模拟云平台（类似 Cloudflare / Google Cloud）官方技术与操作手册 -->
<!-- 该文档包含专有名词、错误码、表格、以及控制台操作路由元数据 -->


# 1. 访问控制与 WAF 规则

## 1.1 自定义 WAF 拦截策略
控制台路径: `/dashboard/security/waf/custom-rules`
CLI 命令: `edge-cli waf rules create`
权限要求: `Security:Admin` 或 `Zone:Edit`

企业版网关提供基于表达式的流量过滤引擎。用户可以通过配置特定规则匹配异常 HTTP 请求。

### 规则字段匹配说明
下表列出了常用的 WAF 匹配字段及其说明：

| 字段名称 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `http.request.uri.path` | String | 请求路径 | `/api/v1/checkout` |
| `ip.geoip.country` | String | 客户端国家代码（ISO 3166-1） | `CN`, `US` |
| `cf.threat_score` | Integer | 综合威胁信誉分（0-100） | `threat_score >= 40` |

注意：拦截动作包括 `BLOCK`（直接返回 403 页面）、`CHALLENGE`（触发人机验证）、`LOG`（仅记录日志不阻断）。对于涉及支付类的核心路径，建议优先使用 `CHALLENGE` 验证码挑战，以避免误伤正常爬虫与代理用户。

## 1.2 跨域资源共享 (CORS) 与 HTTP 响应头
控制台路径: `/dashboard/rules/response-headers`
CLI 命令: `edge-cli rules modify-headers`
权限要求: `Zone:Edit`

跨域请求需要网关层返回特定的响应头。如果前端出现 `Access-Control-Allow-Origin` 缺失报错，请进入控制台添加转换规则。

应当配置的最小响应头集合：
- `Access-Control-Allow-Origin`: 指定受信任域名，严禁在生产带凭证场景下配置为通配符 `*`。
- `Access-Control-Allow-Methods`: 允许的方法，如 `GET, POST, OPTIONS`。
- `Access-Control-Allow-Headers`: 允许携带的自定义请求头。

# 2. 常见系统错误排查指南

## 2.1 边缘网络错误代码 ERR_GATEWAY_502
控制台路径: `/dashboard/analytics/traffic-errors`
CLI 命令: `edge-cli logs query --status 502`
权限要求: `Viewer`

当客户端收到 `ERR_GATEWAY_502` 时，表明边缘节点成功接收请求，但上游源站服务器（Origin Server）返回了无效响应或在预定超时时间内未完成 TCP 握手。

排查步骤：
1. 检查源站 Nginx / Apache 进程是否存活。
2. 检查源站防火墙是否误将边缘节点的回源 IP 判定为恶意攻击并封禁。
3. 检查源站与边缘节点之间的 SSL 证书是否有效。如果开启了 Full(Strict) SSL 模式，源站证书过期会直接导致该错误。

## 2.2 速率限制与限流错误 ERR_RATE_LIMIT_429
控制台路径: `/dashboard/security/rate-limiting`
CLI 命令: `edge-cli security rate-limits list`
权限要求: `Security:Edit`

当请求频次超过在控制台配置的每分钟请求阈值时，网关返回 HTTP 429 状态码。若发现正常业务被误封，可在限流配置中将该 IP 范围加入免流放行名单（Allowlist）。

# 3. 计费与资源配额

## 3.1 跨区域流量外网传输费
控制台路径: `/dashboard/billing/usage`
权限要求: `Billing:Admin`

免费计划与专业版计划包含基础流量配额。超出部分将按照每 GB 0.08 美元计算。若通过专用专线互联（Direct Interconnect），流量费用将享受 40% 的折扣。
