"""知识库与控制台 Agent 全生命周期核心数据结构与契约定义

贯穿从“原始文档解析 -> 上下文增强切块 -> 双轨意图路由 -> 混合检索召回 -> 交叉精排 -> 溯源生成”
各阶段的标准契约体系。
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TypedDict


@dataclass
class ActionLink:
    """【阶段 0/3: 动作定义与路由】控制台操作直达导航与动作定义（类似 Cloudflare/Google Cloud Console 路由）"""
    console_path: str                           # 控制台前端页面路由绝对路径 (例如: "/dashboard/security/waf/custom-rules")
    cli_command: Optional[str] = None           # 对应的终端命令行指令 (例如: "edge-cli waf rules list")
    required_permission: Optional[str] = None   # 执行或访问该页面所需的 RBAC 权限 (例如: "Security:Admin")


class ParsedSection(TypedDict, total=False):
    """【阶段 1: 文档解析契约】将各格式文档统一转换出的结构化章节字典 (支持任意 H1~H6 深度)"""
    doc_title: str                              # 文档根标题 (来源于 FrontMatter title 或文件名)
    heading: str                                # 当前章节直接标题名 (支持 H1~H6 任意级别，如 "1.1 自定义 WAF 拦截策略")
    level: int                                  # 当前标题层级深度 (1 ~ 6，用于动态层级出栈与树形结构还原)
    heading_path: List[str]                     # 动态面包屑路径栈 (如: ["云原生网络手册", "1. 访问控制", "1.1 WAF 规则"])
    content: str                                # 该小节包含的原始 Markdown 正文内容 (纯净正文，不含 HTML 污染)
    action_link: Optional[ActionLink]           # 该章节中提取出的关联控制台操作链接与权限元数据
    metadata: Dict[str, Any]                    # 文档级元数据字典 (如 author, version, category, last_updated)
    parser_strategy: str                        # 生成此切片的底层适配器名称 (如 "markdown_it_ast", "heuristic_fsm")


@dataclass
class UserContext:
    """【企业级多租户与安全契约】当前提问用户的身份、所属租户与 RBAC 权限集合"""
    user_id: str = "guest_user"
    tenant_id: str = "public"                   # 租户隔离标识 (如 "dept_devops", "dept_finance", "public")
    roles: List[str] = field(default_factory=lambda: ["Viewer"]) # 用户拥有的角色清单 (如 ["Viewer", "Security:Admin"])
    permissions: List[str] = field(default_factory=list)         # 具体的权限字符串集合

    def has_permission(self, required_permission: Optional[str]) -> bool:
        """判定用户是否具备该切片或动作所需的权限 (公共切片对全员开放)"""
        if not required_permission or required_permission.lower() in ["none", "public", "any"]:
            return True
        all_perms = set(self.roles + self.permissions)
        if "Admin" in all_perms or "*:*" in all_perms:
            return True
        if required_permission in all_perms:
            return True
        req_domain = required_permission.split(":")[0] if ":" in required_permission else required_permission
        for p in all_perms:
            if p.startswith(f"{req_domain}:Admin"):
                return True
        return False


@dataclass
class Chunk:
    """【阶段 2: 切片与存储契约】知识文本切片（支持上下文增强与 Small-to-Big 父子块架构）"""
    chunk_id: str                               # 全局唯一切片标识符 (如 "doc_cloud_parent_1_child_0")
    doc_id: str                                 # 所属根文档唯一标识 (如 "doc_cloud_platform_v2026")
    title: str                                  # 切片人类可读标题 (通常由层级面包屑组合而成)
    breadcrumbs: List[str]                      # 面包屑层级导航路径 (用于溯源引用与 Prompt 注入)
    raw_content: str                            # 未拼接前缀的切片纯净正文 (表格/段落原子切片)
    contextual_prefix: str                      # 动态注入的全局上下文路径前缀 (如 "[上下文路径: 手册 > 1. WAF > 1.1 规则]")
    parent_id: Optional[str] = None             # 指向父块的指针 (若自身是父块则为 None；子块凭此实现 Small-to-Big 还原)
    is_parent: bool = False                     # 标识是否为父级粗粒度大块 (True 表示完整章节阅读块，False 表示高精检索子块)
    action_link: Optional[ActionLink] = None   # 挂载的操作直达链接 (在切片检索命中时透传给下游渲染卡片)
    tenant_id: str = "public"                   # 归属租户 ID (默认公共切片，支持私有切片隔离)
    metadata: Dict[str, Any] = field(default_factory=dict) # 继承自文档的扩展元数据 (用于多租户与 RBAC 检索前置过滤)

    @property
    def required_permission(self) -> Optional[str]:
        """切片所需的最小 RBAC 权限"""
        if self.action_link and self.action_link.required_permission:
            return self.action_link.required_permission
        return self.metadata.get("required_permission")

    @property
    def contextualized_content(self) -> str:
        """带面包屑路径与上下文增强的文本，用于生成高质量向量和 BM25 倒排索引"""
        if self.contextual_prefix:
            return f"{self.contextual_prefix}\n{self.raw_content}"
        return self.raw_content


@dataclass
class DiagnosticTask:
    """【阶段 3.1: 诊断意图契约】由路由器识别出的待执行系统诊断任务"""
    tool_name: str                               # 目标工具名称 (例如 "inspect_ssl_cert", "check_origin_health")
    params: Dict[str, Any] = field(default_factory=dict) # 调用参数字典 (如 {"domain": "api.example.com"})
    rationale: str = ""                         # 为什么需要触发该诊断的意图解释


@dataclass
class DiagnosticResult:
    """【阶段 3.2: 诊断执行契约】运维监控与探针 API 动态返回的实时指标与健康状态"""
    tool_name: str                              # 执行的工具标识符
    status: str                                 # 诊断结论 ('HEALTHY' | 'WARNING' | 'CRITICAL' | 'UNKNOWN')
    summary: str                                # 人类可读的诊断简述 (如 "源站 SSL 证书已过期 2 天")
    metrics: Dict[str, Any] = field(default_factory=dict) # 结构化关键指标字典 (如 {"days_left": -2, "tls_version": "1.3"})
    latency_ms: float = 0.0                     # 诊断探针远程或本地 API 调用耗时
    suggested_action: Optional[ActionLink] = None # 诊断发现异常后建议的直达处置链接与 CLI 命令


@dataclass
class NavigationIntent:
    """【阶段 3: 路由决策契约】快慢双轨意图识别与控制台分流结果"""
    is_fast_path: bool                          # 是否命中毫秒级快轨 (True: 直达控制台不走大模型; False: 复杂知识问答走 RAG)
    matched_action: Optional[ActionLink] = None # 快轨命中时对应的控制台直达动作与权限
    target_name: Optional[str] = None           # 命中的功能/页面显示名称 (如 "自定义 WAF 拦截策略")
    confidence: float = 0.0                     # 意图分类置信度得分 (0.0 ~ 1.0)
    diagnostic_tasks: List[DiagnosticTask] = field(default_factory=list) # 慢轨时需并发触发的实时诊断工具清单


@dataclass
class SearchResult:
    """【阶段 4: 初筛召回契约】稀疏(BM25)/稠密(向量)/混合(RRF)第一轮检索候选"""
    chunk: Chunk                                # 检索命中的细粒度知识切片 (通常是带上下文的子块)
    score: float                                # 原始检索得分 (BM25 词频分数、向量余弦相似度或 RRF 倒数排名融合分)
    rank: int                                   # 在该路检索结果集中的绝对排序名次 (从 1 开始)
    source_type: str                            # 召回通道来源类型 ('bm25' | 'dense_vector' | 'rrf_hybrid')


@dataclass
class RerankResult:
    """【阶段 5: 精排过滤契约】Cross-Encoder 交叉注意力重排与降噪结果"""
    chunk: Chunk                                # 经过精排打分筛选后保留的高价值切片
    relevance_score: float                      # 归一化语义相关度置信度得分 (0.0 ~ 1.0，低于阈值直接阻断过滤)
    rationale: str                              # 重排判定依据或注意力特征解释 (用于系统可观测性与排错日志)
