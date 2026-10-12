"""快慢双轨路由器 (Fast-Track vs Slow-Track Intent Router)
实现类似 Cloudflare / Google Cloud Console 控制台的意图分流：
- 快轨（Fast Path）: 用户想要找页面、跳转菜单、执行命令 -> 毫秒级直达（不走大模型）。
- 慢轨（Slow Path）: 用户提出疑难问题、原理排查、配置指导 -> 触发 RAG 知识库问答。
"""
import re
from typing import List, Dict, Optional
from ..models import ActionLink, NavigationIntent, Chunk, DiagnosticTask


class IntentRouter:
    """控制台意图识别与快速导航分流器 (支持快轨直达与慢轨动态诊断编排)"""

    # 预先根据文档中提取的操作路径建立映射索引
    def __init__(self, action_registry: Optional[Dict[str, ActionLink]] = None):
        self.action_registry: Dict[str, ActionLink] = action_registry or {}
        # 常见操作动词模式（指示用户正在寻找操作位置而非寻求长篇解答）
        self.action_keywords = ["打开", "跳转", "去", "查看", "进入", "配置页面", "设置入口", "控制台", "在哪", "位置"]

    def register_actions_from_chunks(self, chunks: List[Chunk]):
        """从解析入库的切片元数据中注册所有控制台页面路由"""
        for c in chunks:
            if c.action_link:
                # 以标题和章节作为路由名称
                key = c.title.lower()
                self.action_registry[key] = c.action_link
                for bc in c.breadcrumbs:
                    self.action_registry[bc.lower()] = c.action_link

    @staticmethod
    def rewrite_query_with_history(query: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """多轮对话指代消解与 Query 补充重写"""
        if not history:
            return query

        pronouns = ["这个", "该", "它", "刚才", "之前", "上述", "那", "这里"]
        has_pronoun = any(p in query for p in pronouns)
        is_short_followup = len(query.strip()) <= 15 and any(w in query for w in ["呢", "怎么", "如何", "如果是", "在哪", "查看"])

        if not (has_pronoun or is_short_followup):
            return query

        last_user_query = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_query = msg.get("content", "")
                break

        if not last_user_query:
            return query

        core_entities = re.findall(
            r"([A-Za-z0-9_\-\.]*[\u4e00-\u9fa5]*(?:变压器|互感器|规程|证书|规则|防火墙|日志|网关|waf|cors)|ERR_[A-Za-z0-9_]+|[A-Za-z0-9_\-\.]+)",
            last_user_query,
            re.IGNORECASE
        )
        extracted = [e for e in core_entities if len(e) > 1 and e.lower() not in ["怎么", "如何", "为什么", "查看", "打开", "是多少"]]

        if extracted:
            domain_matches = [
                e for e in extracted
                if any(k in e.lower() for k in ["变压器", "互感器", "规程", "证书", "规则", "防火墙", "日志", "网关", "waf", "cors", "502", "429", "err_"])
            ]
            primary_entity = domain_matches[0] if domain_matches else extracted[0]
            return f"针对【{primary_entity}】，{query}"
        return query

    def route(self, user_query: str, history: Optional[List[Dict[str, str]]] = None) -> NavigationIntent:
        """快速判断用户查询是属于【快轨直接跳转】还是【慢轨知识问答+系统动态诊断】"""
        if history:
            user_query = self.rewrite_query_with_history(user_query, history)

        query_clean = user_query.strip().lower()

        # 1. 检测是否有明显的短语/操作意图
        is_short_command = len(query_clean) <= 15
        has_action_verb = any(v in query_clean for v in self.action_keywords)

        # 2. 模式匹配预置的高频控制台与工业生产管理系统路由
        patterns = [
            (r"(waf|防火墙|拦截规则|自定义规则)", "/dashboard/security/waf/custom-rules", "自定义 WAF 拦截策略", "Security:Admin"),
            (r"(cors|跨域|响应头|header)", "/dashboard/rules/response-headers", "跨域与响应头修改", "Zone:Edit"),
            (r"(502|错误日志|网关错误|流量日志)", "/dashboard/analytics/traffic-errors", "错误日志与流量监控", "Viewer"),
            (r"(限流|429|rate limit|防刷)", "/dashboard/security/rate-limiting", "速率限制与限流配置", "Security:Edit"),
            (r"(账单|费用|计费|配额|usage)", "/dashboard/billing/usage", "计费与用量统计", "Billing:Admin"),
            # 传统垂直行业（电力与特种装备生产管理）系统快轨
            (r"(pms|缺陷|缺陷工单|填报|报修|设备缺陷)", "/pms/equipment/defect-report", "PMS2.0 设备缺陷填报中心", "Equipment:Operator"),
            (r"(scada|在线色谱|色谱监测|实时大盘|遥测曲线)", "/scada/monitoring/dga-realtime", "SCADA 在线油色谱遥测大盘", "Dispatcher:Viewer"),
            (r"(温升|绕组温度|油温监控|顶层油温)", "/scada/monitoring/temperature-metrics", "变压器多测点温升监视", "Maintenance:Viewer"),
            (r"(注意值|限值标准|基线标准)", "/pms/standard/attention-limits", "充油电气设备规程注意值限值台账", "Equipment:Admin"),
        ]

        if is_short_command or has_action_verb:
            # 优先检查是否命中快速直达规则
            for pattern, path, name, perm in patterns:
                if re.search(pattern, query_clean):
                    # 如果用户带有深层疑问词（如“为什么”、“怎么”、“如何”、“排查”、“权限”），则不能当做纯快轨
                    slow_path_triggers = ["为什么", "怎么", "如何", "排查", "原理", "详细说明", "权限", "角色", "原因", "折扣", "分析"]
                    if any(w in query_clean for w in slow_path_triggers):
                        break

                    return NavigationIntent(
                        is_fast_path=True,
                        matched_action=ActionLink(console_path=path, required_permission=perm),
                        target_name=name,
                        confidence=0.95
                    )

        # 3. 慢轨处理：意图编排系统动态诊断任务 (Orchestrated Diagnostics)
        diagnostic_tasks: List[DiagnosticTask] = []

        # 场景 A: 502 网关超时与回源报错排查
        if any(w in query_clean for w in ["502", "err_gateway_502", "网关错误", "握手超时", "源站响应"]):
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="check_origin_health",
                params={"domain": "api.example.com"},
                rationale="排查源站 Nginx/Apache 进程是否存活与本地端口连通性"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="inspect_ssl_cert",
                params={"domain": "api.example.com"},
                rationale="排查源站与边缘节点之间的 SSL 证书是否有效与过期中断"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="query_traffic_metrics",
                params={"error_code": "502", "window": "5m"},
                rationale="统计当前网关近 5 分钟 502 错误率分布与受影响路由"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="check_firewall_blocks",
                params={},
                rationale="排查源站防火墙是否误封边缘回源 IP"
            ))

        # 场景 B: 429 频次受限与防刷排查
        elif any(w in query_clean for w in ["429", "限流", "rate limit", "防刷"]):
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="check_rate_limit_status",
                params={"zone_id": "zone-prod-01"},
                rationale="检查限流规则拦截计数与令牌桶溢出状态"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="query_traffic_metrics",
                params={"error_code": "429", "window": "5m"},
                rationale="统计被拦截的客户端 IP 与接口分布"
            ))

        # 场景 C: 流量突增与 DDoS 攻击排查
        elif any(w in query_clean for w in ["ddos", "攻击", "泛洪", "syn flood", "清洗"]):
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="query_traffic_metrics",
                params={"error_code": "403", "window": "5m"},
                rationale="监控边缘节点当前清洗流量峰值与基线偏离度"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="check_firewall_blocks",
                params={},
                rationale="检查安全规则防护状态"
            ))

        # 场景 D: 传统工业变压器故障、瓦斯继电器动作与油色谱超标确诊
        elif any(w in query_clean for w in ["瓦斯", "继电器", "跳闸", "油色谱", "乙炔", "c2h2", "产气", "电弧", "过热", "dga"]):
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="query_dga_chromatography",
                params={"device_id": "T2-500KV-MAIN"},
                rationale="调用在线油色谱监测装置采集 7 种特征气体浓度与产气速率"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="check_buchholz_relay",
                params={"device_id": "T2-500KV-MAIN"},
                rationale="检查轻重瓦斯继电器接点闭合与油流流速传感器状态"
            ))
            diagnostic_tasks.append(DiagnosticTask(
                tool_name="inspect_transformer_temperature",
                params={"device_id": "T2-500KV-MAIN"},
                rationale="采集变压器顶层油温与高低压绕组光纤温升数据"
            ))

        return NavigationIntent(
            is_fast_path=False,
            confidence=0.1,
            diagnostic_tasks=diagnostic_tasks
        )
