"""运维监控与动态诊断工具注册中心 (Diagnostic Tool Registry)

实现 Orchestrated Parallel Tool-RAG 架构中的动态诊断探针：
1. 源站连通性与服务存活探针 (check_origin_health)
2. SSL/TLS 证书有效性与握手审计探针 (inspect_ssl_cert)
3. 边缘网关实时流量与错误率指标探针 (query_traffic_metrics)
4. 源站防火墙拦截状态探针 (check_firewall_blocks)
5. 速率限制与防刷策略命中探针 (check_rate_limit_status)
并支持多任务线程池并发异步调用，控制端到端诊断延迟在 1ms 以内。
"""
import time
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from ...models import DiagnosticResult, DiagnosticTask, ActionLink


class DiagnosticToolRegistry:
    """系统动态诊断工具注册中心与并发执行器"""

    def __init__(self):
        self._tools: Dict[str, Callable[..., DiagnosticResult]] = {}
        self._tool_descriptions: Dict[str, str] = {}
        self._register_default_tools()

    def register_tool(self, name: str, description: str, func: Callable[..., DiagnosticResult]):
        """注册诊断工具"""
        self._tools[name] = func
        self._tool_descriptions[name] = description

    def get_tool(self, name: str) -> Optional[Callable[..., DiagnosticResult]]:
        return self._tools.get(name)

    def execute_tool(self, name: str, **kwargs) -> DiagnosticResult:
        """同步执行单个诊断工具"""
        func = self.get_tool(name)
        if not func:
            return DiagnosticResult(
                tool_name=name,
                status="UNKNOWN",
                summary=f"未找到指定的诊断工具: {name}",
                latency_ms=0.0
            )

        t0 = time.perf_counter()
        try:
            res = func(**kwargs)
            res.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return res
        except Exception as e:
            return DiagnosticResult(
                tool_name=name,
                status="CRITICAL",
                summary=f"诊断执行抛出异常: {str(e)}",
                latency_ms=round((time.perf_counter() - t0) * 1000, 2)
            )

    def execute_tasks_parallel(
        self,
        tasks: List[DiagnosticTask],
        max_workers: int = 4,
        timeout_seconds: Optional[float] = None
    ) -> List[DiagnosticResult]:
        """使用线程池并发异步执行所有待诊断任务，支持超时保护与异常降级"""
        if not tasks:
            return []

        results: List[DiagnosticResult] = []
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_to_task = {
                executor.submit(self.execute_tool, t.tool_name, **t.params): t
                for t in tasks
            }
            try:
                for future in as_completed(future_to_task, timeout=timeout_seconds):
                    try:
                        res = future.result()
                        results.append(res)
                    except Exception as e:
                        task = future_to_task[future]
                        results.append(DiagnosticResult(
                            tool_name=task.tool_name,
                            status="UNKNOWN",
                            summary=f"并发执行失败: {str(e)}"
                        ))
            except TimeoutError:
                # 针对超时的未完成任务进行熔断降级
                completed_tasks = {r.tool_name for r in results}
                for f, task in future_to_task.items():
                    if task.tool_name not in completed_tasks:
                        f.cancel()
                        results.append(DiagnosticResult(
                            tool_name=task.tool_name,
                            status="TIMEOUT",
                            summary=f"诊断探针调用超时 (>{timeout_seconds}s)，已触发熔断降级"
                        ))
        finally:
            executor.shutdown(wait=False)

        # 按原本的任务顺序保持输出一致性
        task_order = {t.tool_name: idx for idx, t in enumerate(tasks)}
        results.sort(key=lambda r: task_order.get(r.tool_name, 999))
        return results

    @staticmethod
    def format_diagnostics_for_prompt(results: List[DiagnosticResult]) -> str:
        """将结构化诊断指标转换为大模型易于归因与因果推断的 XML 上下文"""
        if not results:
            return ""

        blocks = ["<runtime_diagnostics>"]
        for idx, r in enumerate(results, 1):
            metrics_str = ", ".join([f"{k}={v}" for k, v in r.metrics.items()])
            action_desc = ""
            if r.suggested_action:
                action_desc = f" | 建议修复路径: {r.suggested_action.console_path} (CLI: `{r.suggested_action.cli_command}`)"
            blocks.append(
                f'  <probe index="{idx}" tool="{r.tool_name}" status="{r.status}">\n'
                f'    [简述]: {r.summary}\n'
                f'    [指标]: {metrics_str}{action_desc}\n'
                f'  </probe>'
            )
        blocks.append("</runtime_diagnostics>")
        return "\n".join(blocks)

    def _register_default_tools(self):
        """注册云原生控制台核心默认诊断工具"""

        # 工具 1: 源站健康与进程存活探测
        def check_origin_health(domain: str = "api.example.com", cluster: str = "us-east-cluster") -> DiagnosticResult:
            # 模拟探针调用源站监控 Agent
            return DiagnosticResult(
                tool_name="check_origin_health",
                status="HEALTHY",
                summary="源站 Nginx 进程存活且端口 80/443 本地监听正常，内部 HTTP 本地健康检查返回 200 OK",
                metrics={
                    "origin_ip": "192.0.2.88",
                    "nginx_status": "RUNNING",
                    "cpu_usage": "14.2%",
                    "memory_used_mb": 240,
                    "local_latency_ms": 3.8
                }
            )

        # 工具 2: SSL/TLS 证书生命周期与握手排查
        def inspect_ssl_cert(domain: str = "api.example.com") -> DiagnosticResult:
            # 模拟探针调用边缘与源站证书管理器
            # 设定典型故障：源站 SSL 证书在 2 天前已过期，导致 Full(Strict) 握手失败
            return DiagnosticResult(
                tool_name="inspect_ssl_cert",
                status="CRITICAL",
                summary="源站 SSL 证书已于 2 天前过期（2026-09-27），当前 Full(Strict) SSL 模式强制校验源站证书，直接导致握手中断与 502 报错",
                metrics={
                    "domain": domain,
                    "issuer": "Let's Encrypt Authority X3",
                    "valid_until": "2026-09-27 00:00:00 UTC",
                    "days_remaining": -2,
                    "ssl_mode": "Full(Strict)",
                    "handshake_result": "SSL_ERROR_CERT_EXPIRED"
                },
                suggested_action=ActionLink(
                    console_path="/dashboard/ssl/edge-certificates",
                    cli_command=f"edge-cli certs renew --domain {domain}",
                    required_permission="Security:Admin"
                )
            )

        # 工具 3: 边缘网关实时流量与错误率分析
        def query_traffic_metrics(error_code: str = "502", window: str = "5m") -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="query_traffic_metrics",
                status="WARNING",
                summary=f"近 {window} 内 {error_code} 报错率异常突增，错误率达 41.2%（基线通常 < 0.05%）",
                metrics={
                    "error_code": error_code,
                    "error_rate": "41.2%",
                    "failed_requests": 2840,
                    "spike_start": "2 分钟前",
                    "impacted_routes": ["/api/v1/checkout", "/api/v1/user"]
                },
                suggested_action=ActionLink(
                    console_path="/dashboard/analytics/traffic-errors",
                    cli_command=f"edge-cli logs query --status {error_code}",
                    required_permission="Viewer"
                )
            )

        # 工具 4: 防火墙与拦截日志排查
        def check_firewall_blocks(ip: Optional[str] = None) -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="check_firewall_blocks",
                status="HEALTHY",
                summary="边缘节点回源 IP 段在源站防火墙白名单内，未发现源站 iptables 封禁回源流量",
                metrics={
                    "firewall_type": "iptables / SecurityGroup",
                    "blocked_edge_ips": 0,
                    "waf_mode": "ACTIVE"
                }
            )

        # 工具 5: 速率限制限流桶状态探测
        def check_rate_limit_status(zone_id: str = "zone-prod-01") -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="check_rate_limit_status",
                status="WARNING",
                summary="检测到规则 'API-Rate-Limit-Sensitive' 当前处于限流触发状态，过去 1 分钟拦截 320 次超频请求",
                metrics={
                    "zone_id": zone_id,
                    "trigger_count_1m": 320,
                    "threshold_per_min": 300,
                    "action_taken": "HTTP 429"
                },
                suggested_action=ActionLink(
                    console_path="/dashboard/security/rate-limiting",
                    cli_command="edge-cli security rate-limits list",
                    required_permission="Security:Edit"
                )
            )

        # 工业探针 1: 变压器在线油色谱 7 种特征气体遥测探针
        def query_dga_chromatography(device_id: str = "T2-500KV-MAIN") -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="query_dga_chromatography",
                status="CRITICAL",
                summary="在线油色谱装置遥测到乙炔 (C2H2) 突增至 28.6 μL/L (严重超注意值 1.0 μL/L)，总烃达 385 μL/L，产气速率急剧上升",
                metrics={
                    "device_id": device_id,
                    "h2_ppm": 210.5,
                    "ch4_ppm": 88.2,
                    "c2h6_ppm": 12.1,
                    "c2h4_ppm": 256.0,
                    "c2h2_ppm": 28.6,
                    "thc_ppm": 384.9,
                    "gas_rate_ml_day": 18.5,
                    "iec_ratio_code": "1, 0, 2 (高能电弧放电)"
                },
                suggested_action=ActionLink(
                    console_path="/pms/equipment/defect-report",
                    cli_command="pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL",
                    required_permission="Equipment:Operator"
                )
            )

        # 工业探针 2: 瓦斯继电器动作与油流传感器状态探针
        def check_buchholz_relay(device_id: str = "T2-500KV-MAIN") -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="check_buchholz_relay",
                status="WARNING",
                summary="轻瓦斯继电器接点已闭合发信，集气盒内积聚 45mL 可燃游离气体，重瓦斯跳闸回路保持备用",
                metrics={
                    "device_id": device_id,
                    "light_gas_contact": "CLOSED_ALARM",
                    "heavy_gas_contact": "OPEN_STANDBY",
                    "gas_volume_ml": 45.0,
                    "oil_surge_velocity_ms": 0.42,
                    "flammable_test": "POSITIVE_FLAMMABLE"
                },
                suggested_action=ActionLink(
                    console_path="/scada/monitoring/dga-realtime",
                    cli_command="scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz",
                    required_permission="Dispatcher:Viewer"
                )
            )

        # 工业探针 3: 变压器油温与绕组光纤温升探针
        def inspect_transformer_temperature(device_id: str = "T2-500KV-MAIN") -> DiagnosticResult:
            return DiagnosticResult(
                tool_name="inspect_transformer_temperature",
                status="HEALTHY",
                summary="顶层油温 68.5℃，高压 A/B/C 相绕组光纤热点温升正常，未见大范围过热热点",
                metrics={
                    "device_id": device_id,
                    "top_oil_temp_c": 68.5,
                    "winding_hotspot_c": 82.1,
                    "ambient_temp_c": 28.0,
                    "cooling_fans_status": "AUTO_RUNNING"
                }
            )

        self.register_tool("check_origin_health", "源站服务器存活与进程健康检查", check_origin_health)
        self.register_tool("inspect_ssl_cert", "源站与边缘 SSL 证书状态与过期时间检查", inspect_ssl_cert)
        self.register_tool("query_traffic_metrics", "边缘网关特定错误码实时流量与突增监控", query_traffic_metrics)
        self.register_tool("check_firewall_blocks", "源站防火墙对边缘回源 IP 的封禁排查", check_firewall_blocks)
        self.register_tool("check_rate_limit_status", "速率限制规则触发与超频拦截排查", check_rate_limit_status)
        self.register_tool("query_dga_chromatography", "在线油色谱 7 种特征气体与产气速率遥测探针", query_dga_chromatography)
        self.register_tool("check_buchholz_relay", "瓦斯继电器轻重瓦斯动作与集气盒遥测探针", check_buchholz_relay)
        self.register_tool("inspect_transformer_temperature", "变压器油温与绕组光纤热点温升遥测探针", inspect_transformer_temperature)
