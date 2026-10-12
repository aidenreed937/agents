#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
面试备战手册自动化构建脚本 (体验极致优化版)
- 记忆强化：每张卡片增加【90s 口述核心记忆词链 (Memory Anchors)】
- 布局呼吸感：优化行高、容器内边距与留白，彻底解决高信息量卡片底部紧凑问题
- 打印对比度：强化 Callout 左侧识别边线与深黑字重，完美兼容彩色与黑白打印
- 视觉美化：封面增加目录章节导航与工业级排版细节
"""

import os
import re
import html
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_HTML = BASE_DIR / "interview-handbook.html"
OUTPUT_PDF = BASE_DIR / "interview-handbook.pdf"

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

# 18 张 P0 卡片的专属【90秒口述核心记忆词链】映射字典
MEMORY_ANCHORS = {
    "card-00-01": ["Softmax 温度缩放", "Top-P 核采样截断", "BPE 字节对分词", "KV Cache 显存带宽"],
    "card-01-01": ["隔离止血", "top -Hp 定位", "jstack 堆栈排查", "MAT 支配树分析"],
    "card-01-02": ["AOP 代理机制", "避免类自调用", "严禁大模型长事务", "三道防线幂等"],
    "card-01-03": ["MESI 缓存一致", "lock 汇编内存屏障", "DCL 防指令重排", "线程池背压监控"],
    "card-02-01": ["任务后台解耦", "单调递增序号", "Last-Event-ID 补发", "网关超时保活"],
    "card-02-02": ["Ref/函数式更新", "rAF 帧率批处理", "局部叶子组件隔离", "动态测量虚拟滚动"],
    "card-02-03": ["双令牌轮转 RTR", "401 拦截并发挂起", "垂直 RBAC 注解拦截", "水平租户强制隔离"],
    "card-03-01": ["单库 ACID 事务", "HNSW 内存驻留", "行级安全隔离 RLS", "避免跨系统双库同步"],
    "card-03-02": ["先更库再删缓存", "Canal Binlog 异步补偿", "Lua 原子防误删", "Fencing Token 防并发"],
    "card-03-03": ["Rows 统计偏差诊断", "三大扫描算法选型", "work_mem 磁盘溢出治理", "Keyset 游标分页"],
    "card-04-01": ["RPM+TPM 双令牌桶", "两阶段预扣结算", "上游 429 指数退避+Jitter", "租户公平配额硬熔断"],
    "card-04-02": ["W-TinyLFU 频次衰减", "HNSW 图连边权衡", "RRF 排名非参融合", "双维度令牌惰性结算", "AC 自动机双数组压缩"],
    "card-05-01": ["错误四级分类", "结构化上下文自纠错", "写操作全局幂等键", "最大步数熔断保护"],
    "card-05-02": ["高危动作两阶段拦截", "Checkpoint 快照落库", "释放工作线程资源", "Webhook 审批唤醒恢复"],
    "card-05-03": ["BM25 词频字面匹配", "向量语义距离召回", "RRF 互惠排名归一化", "Cross-Encoder 深度打分"],
    "card-05-04": ["Host-Client-Server 解耦", "Stdio/SSE 双传输协议", "工具能力标准发现", "OS 物理沙箱白名单"],
    "card-06-01": ["RAG 评测三元组", "Agent 任务完成率", "Trace/Span 树状耗时", "低成本 CI 回归基准"],
    "card-06-02": ["直接 vs 间接注入", "XML 标签结构化定界", "决策与物理执行权限解耦", "输出金丝雀与 PII 脱敏"],
}

# ==============================================================================
# 服务端 KaTeX 静态预渲染引擎 (零客户端依赖，完全规避 file:// 协议与跨域问题)
# ==============================================================================

class ServerKaTeX:
    def __init__(self, katex_js_path: Path):
        self.katex_js = katex_js_path
        self.cache = {}
        self.available = self._check_available()

    def _check_available(self) -> bool:
        if not self.katex_js.exists():
            return False
        try:
            res = subprocess.run(["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return res.returncode == 0
        except Exception:
            return False

    def batch_prerender(self, formulas: list):
        """批量渲染所有公式并存入内存缓存"""
        if not self.available or not formulas:
            return

        needed = [item for item in formulas if f"{item['type']}:{item['latex']}" not in self.cache]
        if not needed:
            return

        js_script = f"""
        const katex = require('{self.katex_js.resolve()}');
        let input = '';
        process.stdin.on('data', c => input += c);
        process.stdin.on('end', () => {{
            const items = JSON.parse(input);
            const res = {{}};
            for (const it of items) {{
                const key = it.type + ':' + it.latex;
                try {{
                    res[key] = katex.renderToString(it.latex, {{
                        displayMode: it.type === 'block',
                        throwOnError: false
                    }});
                }} catch(e) {{
                    res[key] = it.latex;
                }}
            }}
            process.stdout.write(JSON.stringify(res));
        }});
        """
        try:
            p = subprocess.Popen(
                ["node", "-e", js_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = p.communicate(input=json.dumps(needed))
            if p.returncode == 0:
                results = json.loads(stdout)
                self.cache.update(results)
        except Exception as e:
            print(f"[!] KaTeX 服务端预渲染调用异常: {e}")

    def render(self, latex: str, display: bool = False) -> str:
        key = ("block:" if display else "inline:") + latex
        if key in self.cache:
            return self.cache[key]
        return f"$${latex}$$" if display else f"${latex}$"

KATEX_ENGINE = ServerKaTeX(BASE_DIR / "assets" / "katex" / "katex.min.js")

# ==============================================================================
# 原生工业级矢量 SVG 架构图 (100% 打印保真)
# ==============================================================================

def get_svg_career_narrative() -> str:
    """10年客户端经历资产转化拓扑图"""
    return """
    <div class="diagram-wrapper">
        <div class="diagram-title">能力演进与资产转化拓扑图</div>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 210" width="100%" height="auto" class="responsive-svg">
            <defs>
                <linearGradient id="cnGradTarget" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#0f172a" />
                    <stop offset="100%" stop-color="#1e293b" />
                </linearGradient>
                <linearGradient id="cnGradBlue" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#2563eb" />
                    <stop offset="100%" stop-color="#1d4ed8" />
                </linearGradient>
                <filter id="cnShadow" x="-5%" y="-10%" width="110%" height="130%">
                    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.08"/>
                </filter>
                <marker id="cnArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#2563eb"/>
                </marker>
            </defs>

            <!-- 节点 1: 底层工程沉淀 -->
            <rect x="25" y="15" width="230" height="48" rx="8" fill="#ffffff" stroke="#94a3b8" stroke-width="1.5" filter="url(#cnShadow)"/>
            <circle cx="45" cy="39" r="6" fill="#3b82f6"/>
            <text x="62" y="34" font-size="11.5" font-weight="700" fill="#0f172a">底层系统工程沉淀</text>
            <text x="62" y="50" font-size="9" fill="#64748b">10年 Android · 5年 Java · JVM并发调优</text>

            <!-- 节点 2: 现代全栈交互 -->
            <rect x="25" y="81" width="230" height="48" rx="8" fill="#ffffff" stroke="#2563eb" stroke-width="1.8" filter="url(#cnShadow)"/>
            <circle cx="45" cy="105" r="6" fill="#2563eb"/>
            <text x="62" y="100" font-size="11.5" font-weight="700" fill="#0f172a">现代 Web 全栈交互</text>
            <text x="62" y="116" font-size="9" fill="#64748b">React 18 · TypeScript · SSE 长连接流式管线</text>

            <!-- 节点 3: Agent 应用工程 -->
            <rect x="25" y="147" width="230" height="48" rx="8" fill="#ffffff" stroke="#8b5cf6" stroke-width="1.5" filter="url(#cnShadow)"/>
            <circle cx="45" cy="171" r="6" fill="#8b5cf6"/>
            <text x="62" y="166" font-size="11.5" font-weight="700" fill="#0f172a">Agent 应用工程化</text>
            <text x="62" y="182" font-size="9" fill="#64748b">Tool Calling · 混合 RAG · 状态机 · HITL审批</text>

            <!-- 连接平滑贝塞尔曲线 -->
            <path d="M 255 39 C 330 39, 340 105, 385 105" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-dasharray="4,3"/>
            <path d="M 255 105 L 385 105" fill="none" stroke="#2563eb" stroke-width="2.2" marker-end="url(#cnArrow)"/>
            <path d="M 255 171 C 330 171, 340 105, 385 105" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-dasharray="4,3"/>

            <!-- 汇聚中心卡片 -->
            <rect x="390" y="25" width="325" height="160" rx="12" fill="url(#cnGradTarget)" filter="url(#cnShadow)"/>
            
            <rect x="410" y="42" width="76" height="20" rx="4" fill="url(#cnGradBlue)"/>
            <text x="448" y="56" font-size="9.5" font-weight="700" fill="#ffffff" text-anchor="middle">核心定位</text>
            <text x="496" y="58" font-size="15" font-weight="800" fill="#ffffff">端云全栈 Agent 架构师</text>

            <line x1="410" y1="74" x2="695" y2="74" stroke="#334155" stroke-width="1"/>

            <text x="412" y="98" font-size="10" font-weight="600" fill="#38bdf8">1. 复杂状态机治理：</text>
            <text x="412" y="113" font-size="9.2" fill="#cbd5e1">将客户端页面生命周期/断点续传经验，降维映射至 Agent 状态机</text>

            <text x="412" y="137" font-size="10" font-weight="600" fill="#38bdf8">2. 长连接与高可靠防线：</text>
            <text x="412" y="152" font-size="9.2" fill="#cbd5e1">SSE 序号补发保活、JVM高并发调优、两阶段审批与安全沙箱</text>
            <text x="412" y="169" font-size="8.8" fill="#94a3b8">优势：具备单兵端到端交付复杂业务系统的全栈架构视野</text>
        </svg>
    </div>
    """

def get_svg_system_architecture() -> str:
    """企业知识与业务研究助手系统全景架构图"""
    return """
    <div class="diagram-wrapper">
        <div class="diagram-title">企业知识与业务研究助手 · 系统全景架构图</div>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 430" width="100%" height="auto" class="responsive-svg">
            <defs>
                <filter id="saShadow" x="-2%" y="-4%" width="104%" height="110%">
                    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.06"/>
                </filter>
                <marker id="saArrowBlue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#2563eb"/>
                </marker>
                <marker id="saArrowGray" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b"/>
                </marker>
                <marker id="saArrowPurple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#7c3aed"/>
                </marker>
            </defs>

            <!-- 1. 用户访问层 -->
            <rect x="20" y="12" width="700" height="38" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.2" filter="url(#saShadow)"/>
            <text x="370" y="36" font-size="11.5" font-weight="700" fill="#0f172a" text-anchor="middle">用户终端层：PC Web 浏览器 / 移动端 WebView (支持全屏自适应与触控)</text>

            <!-- 箭头：用户 -> 前端 -->
            <line x1="370" y1="50" x2="370" y2="66" stroke="#64748b" stroke-width="1.8" marker-end="url(#saArrowGray)"/>

            <!-- 2. 前端展示层 -->
            <rect x="20" y="68" width="700" height="72" rx="10" fill="#ffffff" stroke="#2563eb" stroke-width="1.6" filter="url(#saShadow)"/>
            <rect x="20" y="68" width="700" height="24" rx="10" fill="#eff6ff"/>
            <text x="36" y="84" font-size="9.5" font-weight="800" fill="#1d4ed8">前端展示层 (React 18 + TypeScript + Tailwind CSS)</text>
            
            <rect x="36" y="99" width="195" height="30" rx="5" fill="#f8fafc" stroke="#e2e8f0"/>
            <text x="133" y="117" font-size="9" font-weight="600" fill="#0f172a" text-anchor="middle">自适应打字机 UI (TanStack Virtual)</text>

            <rect x="245" y="99" width="235" height="30" rx="5" fill="#f8fafc" stroke="#e2e8f0"/>
            <text x="362" y="117" font-size="9" font-weight="600" fill="#0f172a" text-anchor="middle">rAF 帧率缓冲队列 (Batching Buffer)</text>

            <rect x="494" y="99" width="210" height="30" rx="5" fill="#f8fafc" stroke="#e2e8f0"/>
            <text x="599" y="117" font-size="9" font-weight="600" fill="#0f172a" text-anchor="middle">SSE Client (Last-Event-ID 续传)</text>

            <!-- 连线向下：控制流 vs 数据流 -->
            <path d="M 180 140 L 180 170" fill="none" stroke="#64748b" stroke-width="1.8" marker-end="url(#saArrowGray)"/>
            <text x="140" y="158" font-size="8.5" font-weight="700" fill="#475569">REST 业务控制</text>

            <path d="M 550 140 L 550 170" fill="none" stroke="#2563eb" stroke-width="2" marker-end="url(#saArrowBlue)"/>
            <text x="595" y="158" font-size="8.5" font-weight="700" fill="#2563eb">SSE 流式通道</text>

            <!-- 3. 双后端服务层 (控制面 vs 数据面) -->
            <!-- 3.1 Spring Boot 控制面 -->
            <rect x="20" y="172" width="335" height="135" rx="10" fill="#ffffff" stroke="#0f172a" stroke-width="1.8" filter="url(#saShadow)"/>
            <rect x="20" y="172" width="335" height="26" rx="10" fill="#f1f5f9"/>
            <text x="36" y="189" font-size="10.5" font-weight="800" fill="#0f172a">业务控制面 (Spring Boot 3 + Spring Security)</text>
            
            <text x="36" y="217" font-size="9" fill="#334155"><tspan font-weight="700">用户与权限</tspan>：JWT 双令牌轮转 (RTR) 与 RBAC 权限注解</text>
            <text x="36" y="236" font-size="9" fill="#334155"><tspan font-weight="700">工作区管理</tspan>：企业组织架构、文档上传与元数据审计</text>
            <text x="36" y="255" font-size="9" fill="#334155"><tspan font-weight="700">审批工单流</tspan>：两阶段 Pending Actions 状态机管理</text>
            <text x="36" y="274" font-size="9" fill="#334155"><tspan font-weight="700">事务强隔离</tspan>：严禁长事务包裹外部长耗时大模型调用</text>
            <text x="36" y="293" font-size="8.5" fill="#64748b">连接池防线：HikariCP 动态监控与 CallerRunsPolicy 线程池</text>

            <!-- 3.2 FastAPI AI 运行时 -->
            <rect x="385" y="172" width="335" height="135" rx="10" fill="#ffffff" stroke="#7c3aed" stroke-width="1.8" filter="url(#saShadow)"/>
            <rect x="385" y="172" width="335" height="26" rx="10" fill="#faf5ff"/>
            <text x="401" y="189" font-size="10.5" font-weight="800" fill="#6d28d9">AI 运行时 (FastAPI + Python 3.11)</text>

            <text x="401" y="217" font-size="9" fill="#334155"><tspan font-weight="700">ReAct 运行循环</tspan>：原生多轮推理、工具解析与模型自纠错</text>
            <text x="401" y="236" font-size="9" fill="#334155"><tspan font-weight="700">混合 RAG 管线</tspan>：BM25 + 向量双路召回 + Cross-Encoder 重排</text>
            <text x="401" y="255" font-size="9" fill="#334155"><tspan font-weight="700">状态持久化</tspan>：Checkpoint 状态图序列化落盘与无损唤醒</text>
            <text x="401" y="274" font-size="9" fill="#334155"><tspan font-weight="700">工具拦截器</tspan>：写操作注入幂等键，高危动作阻断抛出工单</text>
            <text x="401" y="293" font-size="8.5" fill="#64748b">安全防线：XML 标签数据定界、输出 PII 脱敏与金丝雀监控</text>

            <!-- 双后端通信连线 -->
            <path d="M 355 240 L 385 240" stroke="#7c3aed" stroke-width="1.8" stroke-dasharray="3,2" marker-end="url(#saArrowPurple)"/>
            <text x="370" y="233" font-size="7.5" font-weight="700" fill="#7c3aed" text-anchor="middle">审批唤醒</text>

            <!-- 4. 存储与外部服务层 -->
            <!-- 统一数据库底座 -->
            <rect x="180" y="328" width="380" height="85" rx="10" fill="#0f172a" filter="url(#saShadow)"/>
            <text x="370" y="352" font-size="11.5" font-weight="800" fill="#ffffff" text-anchor="middle">统一数据与存储底座：PostgreSQL 16 + pgvector</text>
            <text x="370" y="372" font-size="9" fill="#94a3b8" text-anchor="middle">关系业务表 · 租户行级安全隔离 (RLS) · 向量切块表 (HNSW 索引) · Checkpoint 快照</text>
            <text x="370" y="390" font-size="9" fill="#38bdf8" text-anchor="middle">架构护城河：单库 ACID 事务消除跨系统不一致，免除分布式事务中间件</text>
            <text x="370" y="405" font-size="8" fill="#64748b" text-anchor="middle">(辅助选配：Redis 承载短期 SSE 事件补发队列与分布式互斥锁)</text>

            <!-- 外部生态 1: 业务系统 -->
            <rect x="20" y="335" width="140" height="72" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5" filter="url(#saShadow)"/>
            <text x="90" y="360" font-size="10" font-weight="700" fill="#0f172a" text-anchor="middle">企业内部业务系统</text>
            <text x="90" y="378" font-size="8.5" fill="#64748b" text-anchor="middle">ERP / CRM 外部接口</text>
            <text x="90" y="394" font-size="8.5" font-weight="700" fill="#16a34a" text-anchor="middle">全局幂等键防重</text>

            <!-- 外部生态 2: 大模型 -->
            <rect x="580" y="335" width="140" height="72" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5" filter="url(#saShadow)"/>
            <text x="650" y="360" font-size="10" font-weight="700" fill="#0f172a" text-anchor="middle">大模型供应商</text>
            <text x="650" y="378" font-size="8.5" fill="#64748b" text-anchor="middle">OpenAI / Claude / DS</text>
            <text x="650" y="394" font-size="8.5" font-weight="700" fill="#dc2626" text-anchor="middle">RPM/TPM 双令牌限流</text>

            <!-- 连线到数据库与外部系统 -->
            <line x1="160" y1="371" x2="180" y2="371" stroke="#64748b" stroke-width="1.5" marker-end="url(#saArrowGray)"/>
            <line x1="580" y1="371" x2="560" y2="371" stroke="#7c3aed" stroke-width="1.5" marker-end="url(#saArrowPurple)"/>
            <path d="M 180 307 L 230 328" stroke="#64748b" stroke-width="1.5" marker-end="url(#saArrowGray)"/>
            <path d="M 550 307 L 500 328" stroke="#7c3aed" stroke-width="1.5" marker-end="url(#saArrowPurple)"/>
        </svg>
    </div>
    """

# ==============================================================================
# Markdown 解析器 (带记忆锚点词链与紧凑布局控制)
# ==============================================================================

def markdown_to_html(md_text: str, card_key: str = None) -> str:
    """转换 Markdown，并对面试卡核心章节进行专属卡片式包装"""
    
    # 步骤 1: 将所有 Mermaid 代码块安全替换为独立占位符
    md_text = re.sub(
        r'```mermaid[\s\S]*?flowchart LR[\s\S]*?端云全栈 Agent 工程师[\s\S]*?```',
        '\n\n<!-- PLACEHOLDER_CAREER_NARRATIVE -->\n\n',
        md_text
    )
    md_text = re.sub(
        r'```mermaid[\s\S]*?flowchart TD[\s\S]*?```',
        '\n\n<!-- PLACEHOLDER_SYSTEM_ARCHITECTURE -->\n\n',
        md_text
    )

    # 步骤 1.5: 提取数学公式并替换为占位符，防止 Markdown 格式化破坏公式
    math_placeholders = {}
    math_counter = 0

    def extract_block_math(match):
        nonlocal math_counter
        raw = match.group(1).strip()
        ph = f"KATEXBLOCKPH_{math_counter}"
        math_placeholders[ph] = ("block", raw)
        math_counter += 1
        return f"\n\n{ph}\n\n"

    def extract_inline_math(match):
        nonlocal math_counter
        raw = match.group(1).strip()
        ph = f"KATEXINLINEPH_{math_counter}"
        math_placeholders[ph] = ("inline", raw)
        math_counter += 1
        return ph

    md_text = re.sub(r'\$\$(.+?)\$\$', extract_block_math, md_text, flags=re.DOTALL)
    md_text = re.sub(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)', extract_inline_math, md_text)

    lines = md_text.splitlines()
    html_lines = []
    in_code_block = False
    code_lang = ""
    code_buffer = []
    in_table = False
    table_rows = []
    in_list = False
    list_type = "ul"
    in_callout = False
    callout_type = ""

    def flush_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            in_table = False
            table_rows = []
            return ""
        out = ['<div class="table-container"><table class="card-table">']
        header = table_rows[0]
        out.append("<thead><tr>")
        for cell in header:
            out.append(f"<th>{inline_formatting(cell)}</th>")
        out.append("</tr></thead><tbody>")
        for row in table_rows[1:]:
            out.append("<tr>")
            for cell in row:
                out.append(f"<td>{inline_formatting(cell)}</td>")
            out.append("</tr>")
        out.append("</tbody></table></div>")
        in_table = False
        table_rows = []
        return "\n".join(out)

    def flush_list():
        nonlocal in_list, list_type
        if not in_list:
            return ""
        out = f"</{list_type}>"
        in_list = False
        return out

    def close_callout_if_open():
        nonlocal in_callout, callout_type
        if in_callout:
            in_callout = False
            callout_type = ""
            return "</div>"
        return ""

    def inline_formatting(text: str) -> str:
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        text = re.sub(r'^(?:-\s*)?\[ \]\s*', r'<span class="chk-box"></span> ', text)
        text = re.sub(r'^(?:-\s*)?\[x\]\s*', r'<span class="chk-box checked">✓</span> ', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 保护占位符不被包裹进 <p> 标签
        if stripped in ["<!-- PLACEHOLDER_CAREER_NARRATIVE -->", "<!-- PLACEHOLDER_SYSTEM_ARCHITECTURE -->"]:
            if in_table:
                html_lines.append(flush_table())
            if in_list:
                html_lines.append(flush_list())
            html_lines.append(close_callout_if_open())
            html_lines.append(stripped)
            i += 1
            continue

        if stripped.startswith("KATEXBLOCKPH_") and stripped in math_placeholders:
            if in_table:
                html_lines.append(flush_table())
            if in_list:
                html_lines.append(flush_list())
            html_lines.append(close_callout_if_open())
            html_lines.append(f'<div class="katex-display-container">{stripped}</div>')
            i += 1
            continue

        # 代码块开始 / 结束
        if stripped.startswith("```"):
            if in_code_block:
                escaped_code = html.escape("\n".join(code_buffer))
                html_lines.append(
                    f'<div class="code-container">'
                    f'<div class="code-header"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="code-lang">{code_lang}</span></div>'
                    f'<pre><code class="language-{code_lang}">{escaped_code}</code></pre></div>'
                )
                code_buffer = []
                in_code_block = False
            else:
                if in_table:
                    html_lines.append(flush_table())
                if in_list:
                    html_lines.append(flush_list())
                in_code_block = True
                code_lang = stripped[3:].strip()
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                html_lines.append(flush_list())
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            if all(re.match(r'^:?-+:?$', c) for c in cells):
                i += 1
                continue
            if not in_table:
                in_table = True
                table_rows = [cells]
            else:
                table_rows.append(cells)
            i += 1
            continue
        elif in_table:
            html_lines.append(flush_table())

        # 标题处理与 Callout 识别
        if stripped.startswith("#"):
            if in_list:
                html_lines.append(flush_list())
            level = len(re.match(r'^#+', stripped).group(0))
            title = stripped[level:].strip()

            if "30 秒电梯回答" in title:
                html_lines.append(close_callout_if_open())
                in_callout = True
                callout_type = "elevator"
                html_lines.append('<div class="callout callout-elevator"><div class="callout-label"><span class="icon">⚡</span> 1. 30 秒电梯口述回答</div>')
            elif "深入原理" in title:
                html_lines.append(close_callout_if_open())
                in_callout = True
                callout_type = "deep"
                html_lines.append('<div class="callout callout-deep"><div class="callout-label"><span class="icon">🔍</span> 2. 深入原理与机制</div>')
            elif "工程取舍" in title:
                html_lines.append(close_callout_if_open())
                in_callout = True
                callout_type = "tradeoff"
                html_lines.append('<div class="callout callout-tradeoff"><div class="callout-label"><span class="icon">⚖️</span> 3. 工程取舍与防线边界</div>')
            elif "高频追问应对" in title:
                html_lines.append(close_callout_if_open())
                in_callout = True
                callout_type = "questions"
                html_lines.append('<div class="callout callout-questions"><div class="callout-label"><span class="icon">🎯</span> 4. 高频追问深挖应对</div>')
            elif "自测标准" in title:
                html_lines.append(close_callout_if_open())
                in_callout = True
                callout_type = "check"
                html_lines.append('<div class="callout callout-check"><div class="callout-label"><span class="icon">⏱️</span> 5. 90 秒自测标准</div>')
            else:
                html_lines.append(close_callout_if_open())
                html_lines.append(f'<h{level}>{inline_formatting(title)}</h{level}>')
            i += 1
            continue

        # 水平分割线
        if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped):
            if in_list:
                html_lines.append(flush_list())
            html_lines.append(close_callout_if_open())
            html_lines.append('<hr class="divider"/>')
            i += 1
            continue

        # 列表处理
        list_match = re.match(r'^[*-]\s+(.*)$', stripped)
        num_match = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if list_match or num_match:
            cur_type = "ol" if num_match else "ul"
            content = num_match.group(2) if num_match else list_match.group(1)
            num_val = int(num_match.group(1)) if num_match else 1
            start_attr = f' start="{num_val}"' if cur_type == "ol" and num_val > 1 else ''
            if not in_list:
                in_list = True
                list_type = cur_type
                html_lines.append(f'<{list_type}{start_attr}>')
            elif in_list and list_type != cur_type:
                html_lines.append(flush_list())
                in_list = True
                list_type = cur_type
                html_lines.append(f'<{list_type}{start_attr}>')

            if callout_type == "questions":
                if "追问" in content:
                    html_lines.append(f'<li class="qa-question">{inline_formatting(content)}</li>')
                elif "应对" in content or "核心逻辑" in content:
                    html_lines.append(f'<li class="qa-answer">{inline_formatting(content)}</li>')
                else:
                    html_lines.append(f'<li class="qa-sub">{inline_formatting(content)}</li>')
            else:
                html_lines.append(f'<li>{inline_formatting(content)}</li>')
            i += 1
            continue
        elif in_list and stripped == "":
            pass
        elif in_list:
            html_lines.append(flush_list())

        # 引用块
        if stripped.startswith(">"):
            quote_text = stripped[1:].strip()
            html_lines.append(f'<blockquote>{inline_formatting(quote_text)}</blockquote>')
            i += 1
            continue

        if stripped == "":
            i += 1
            continue

        # 元数据行格式化 (模块 / 难度 / 熟练度)，并在下方自动注入【记忆词链】
        if "**模块**：" in stripped:
            meta_html = re.sub(r'\*\*([^*]+)\*\*：([^\s|]+)', r'<span class="tag-pill"><span class="tag-k">\1</span><span class="tag-v">\2</span></span>', stripped)
            meta_html = meta_html.replace("｜", "")
            
            anchor_html = ""
            if card_key and card_key in MEMORY_ANCHORS:
                chips = " ➔ ".join(f'<span class="anchor-chip">{w}</span>' for w in MEMORY_ANCHORS[card_key])
                anchor_html = f"""
                <div class="memory-anchor-bar">
                    <span class="anchor-label">⚡ 90s 记忆词链：</span>
                    {chips}
                </div>
                """
            
            html_lines.append(f'<div class="card-meta-bar">{meta_html}</div>{anchor_html}')
            i += 1
            continue

        html_lines.append(f'<p>{inline_formatting(stripped)}</p>')
        i += 1

    if in_table:
        html_lines.append(flush_table())
    if in_list:
        html_lines.append(flush_list())
    html_lines.append(close_callout_if_open())

    final_html = "\n".join(html_lines)

    # 步骤 2: 将数学公式占位符替换为预渲染的静态 KaTeX 节点
    for ph, (m_type, latex) in math_placeholders.items():
        is_block = (m_type == "block")
        rendered_node = KATEX_ENGINE.render(latex, display=is_block)
        final_html = final_html.replace(ph, rendered_node)

    # 步骤 3: 将占位符安全替换为完整高精度的原生 SVG
    final_html = final_html.replace("<!-- PLACEHOLDER_CAREER_NARRATIVE -->", get_svg_career_narrative())
    final_html = final_html.replace("<!-- PLACEHOLDER_SYSTEM_ARCHITECTURE -->", get_svg_system_architecture())

    return final_html


def collect_content() -> dict:
    """收集核心文档与面试卡片"""
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "narrative": "",
        "project_story": "",
        "cards": []
    }

    narrative_file = BASE_DIR / "00-roadmap" / "career-transition-narrative.md"
    if narrative_file.exists():
        data["narrative"] = narrative_file.read_text(encoding="utf-8")

    project_file = BASE_DIR / "07-project-stories" / "story-01-enterprise-ai-assistant.md"
    if project_file.exists():
        data["project_story"] = project_file.read_text(encoding="utf-8")

    cards_dir = BASE_DIR / "08-interview-cards"
    if cards_dir.exists():
        for card_path in sorted(cards_dir.glob("card-*.md")):
            content = card_path.read_text(encoding="utf-8")
            data["cards"].append({
                "filename": card_path.name,
                "content": content
            })

    return data


def build_html(data: dict) -> str:
    """构建精美视觉与打印就绪的完整 HTML"""
    # 步骤 0: 统一扫描收集所有文档与卡片中的公式，执行单次批量预渲染
    all_formulas = []
    docs = [data.get("narrative", ""), data.get("project_story", "")] + [c["content"] for c in data.get("cards", [])]
    for doc in docs:
        for bm in re.findall(r'\$\$(.+?)\$\$', doc, re.DOTALL):
            all_formulas.append({"type": "block", "latex": bm.strip()})
        doc_sub = re.sub(r'\$\$.+?\$\$', '', doc, flags=re.DOTALL)
        for im in re.findall(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)', doc_sub):
            all_formulas.append({"type": "inline", "latex": im.strip()})
    KATEX_ENGINE.batch_prerender(all_formulas)

    cards_count = len(data["cards"])
    html_parts = []

    # 1. 封面页 (带章节索引与现代化工业布局)
    html_parts.append(f"""
    <div class="page cover-page">
        <div class="cover-card">
            <div class="badge-pill">A4 可打印 · 高频口述速记手册</div>
            <h1 class="cover-title">高级全栈与 Agent 应用工程师<br/><span class="text-gradient">面试通关通识备战手册</span></h1>
            <p class="cover-desc">10年客户端/Java工程底蕴资产化 · 核心架构剖析 · P0 可打印单页面试卡</p>
            
            <div class="grid-stats">
                <div class="stat-box">
                    <div class="stat-num">{cards_count}</div>
                    <div class="stat-label">P0 核心面试卡</div>
                </div>
                <div class="stat-box">
                    <div class="stat-num">100%</div>
                    <div class="stat-label">单页闭卷可口述</div>
                </div>
                <div class="stat-box">
                    <div class="stat-num">30天</div>
                    <div class="stat-label">首发试投时间线</div>
                </div>
            </div>

            <div class="cover-meta-table">
                <div class="meta-row">
                    <span class="meta-th">核心技术栈</span>
                    <span class="meta-td">Java 17 (Spring Boot 3) · React 18 (TypeScript) · PostgreSQL (pgvector) · FastAPI (Python Agent)</span>
                </div>
                <div class="meta-row">
                    <span class="meta-th">复习策略</span>
                    <span class="meta-td">单面打印卡片页，背面留白手写红笔批注；每天离开椅子站立闭卷口述 90 秒</span>
                </div>
                <div class="meta-row">
                    <span class="meta-th">更新编译时间</span>
                    <span class="meta-td">{data['generated_at']} (已同步最新知识库与记忆词链)</span>
                </div>
            </div>

            <div class="cover-quote">
                “Prompt 调优决定系统的效果上限，但工程架构与防御机制决定系统的可用性下限。”
            </div>
        </div>
    </div>
    """)

    # 2. 第一部分：核心叙事与能力映射
    if data["narrative"]:
        cleaned_narrative = re.sub(r'^#\s+.*', '', data["narrative"], count=1)
        narrative_html = markdown_to_html(cleaned_narrative)
        html_parts.append(f"""
        <div class="page doc-page">
            <div class="page-top-bar">
                <span class="top-tag">Part I · 求职定位与战略防守</span>
                <span class="top-brand">Interview Handbook</span>
            </div>
            <div class="doc-container">
                {narrative_html}
            </div>
            <div class="page-bottom-bar">
                <span>10 年客户端经历的资产转化策略</span>
                <span>Section 1</span>
            </div>
        </div>
        """)

    # 3. 第二部分：核心实战项目架构全景
    if data["project_story"]:
        cleaned_project = re.sub(r'^#\s+.*', '', data["project_story"], count=1)
        project_html = markdown_to_html(cleaned_project)
        html_parts.append(f"""
        <div class="page doc-page">
            <div class="page-top-bar">
                <span class="top-tag">Part II · 核心主打项目架构复盘</span>
                <span class="top-brand">Enterprise AI Assistant</span>
            </div>
            <div class="doc-container">
                {project_html}
            </div>
            <div class="page-bottom-bar">
                <span>企业知识与业务研究助手 (全栈 + Agent)</span>
                <span>Section 2</span>
            </div>
        </div>
        """)

    # 4. 第三部分：P0 面试卡集（每张卡严格独立一页）
    for idx, card in enumerate(data["cards"], start=1):
        # 提取卡片编号 key (如 card-05-01)
        card_key_match = re.match(r'^(card-\d+-\d+)', card["filename"])
        card_key = card_key_match.group(1) if card_key_match else None

        card_html = markdown_to_html(card["content"], card_key=card_key)
        html_parts.append(f"""
        <div class="page card-page">
            <div class="card-top-header">
                <div class="header-left">
                    <span class="card-badge">P0 卡片 #{idx:02d}</span>
                    <span class="card-src">{card['filename']}</span>
                </div>
                <div class="header-right">
                    <span class="card-timer">90s 口述自测</span>
                </div>
            </div>
            
            <div class="card-content-area">
                {card_html}
            </div>

            <div class="card-bottom-footer">
                <span class="footer-tip">口述训练法：遮盖下方内容，先扫一眼上方“记忆词链”，站立脱稿口述 90 秒</span>
                <span class="footer-counter">Card {idx} of {cards_count}</span>
            </div>
        </div>
        """)

    # 5. 第四部分：附录 - 手写错题打卡页 (2 页)
    for p in range(1, 3):
        html_parts.append(f"""
        <div class="page appendix-page">
            <div class="page-top-bar">
                <span class="top-tag">附录 · 动态错题记录与追问反思 (第 {p} 页)</span>
                <span class="top-brand">Mock & Interview Review</span>
            </div>
            <div class="doc-container">
                <div class="callout callout-elevator" style="margin-bottom: 10px;">
                    <div class="callout-label">📝 手写打卡公约</div>
                    <p style="margin: 2px 0;">每次真实面试或模拟面试结束后 15 分钟内，手写记录当场答得结巴、没能接住的关键追问，晚上集中打补丁。</p>
                </div>
                
                <table class="handwrite-table">
                    <thead>
                        <tr>
                            <th style="width: 14%;">日期 / 公司</th>
                            <th style="width: 22%;">考察模块 / 题目</th>
                            <th style="width: 44%;">现场卡壳追问 / 盲区记录</th>
                            <th style="width: 20%;">针对补漏行动项</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join('<tr><td style="height: 52px;"></td><td></td><td></td><td></td></tr>' for _ in range(11))}
                    </tbody>
                </table>
            </div>
            <div class="page-bottom-bar">
                <span>错题记录与反思打卡页</span>
                <span>Page {p}</span>
            </div>
        </div>
        """)

    body_content = "\n".join(html_parts)

    # 动态加载并内联 KaTeX 样式以确保离线 100% 可用且不受本地 file:// 策略影响
    katex_css_path = BASE_DIR / "assets" / "katex" / "katex.min.css"
    inlined_katex_css = ""
    if katex_css_path.exists():
        raw_css = katex_css_path.read_text(encoding="utf-8")
        inlined_katex_css = raw_css.replace("url(fonts/", "url(assets/katex/fonts/")

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>高级全栈与 Agent 应用工程师 面试通关手册</title>
    <!-- KaTeX 数学公式支持 (已静态预渲染 MathML+DOM，同时提供样式与客户端动态兜底) -->
    <link rel="stylesheet" href="assets/katex/katex.min.css" onerror="this.onerror=null;this.href='https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';">
    <script defer src="assets/katex/katex.min.js" onerror="this.onerror=null;var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';s.defer=true;document.head.appendChild(s);"></script>
    <script defer src="assets/katex/auto-render.min.js" onerror="this.onerror=null;var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js';s.defer=true;document.head.appendChild(s);"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            function renderMath() {{
                if (typeof renderMathInElement === "function") {{
                    renderMathInElement(document.body, {{
                        delimiters: [
                            {{left: "$$", right: "$$", display: true}},
                            {{left: "$", right: "$", display: false}},
                            {{left: "\\\\(", right: "\\\\)", display: false}},
                            {{left: "\\\\[", right: "\\\\]", display: true}}
                        ],
                        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
                        throwOnError: false
                    }});
                }} else {{
                    setTimeout(renderMath, 60);
                }}
            }}
            renderMath();
        }});
    </script>
    <style>
        /* 内联 KaTeX 样式 (保证零外部请求开箱即用) */
        {inlined_katex_css}

        /* KaTeX 紧凑排版适配与展示块容器 */
        .katex-display-container {{
            text-align: center;
            margin: 3px 0;
            overflow-x: auto;
            overflow-y: hidden;
        }}
        .katex {{ font-size: 1.02em; line-height: 1.2; }}
        .katex-display {{ margin: 2px 0 !important; }}
        @page {{
            size: A4 portrait;
            margin: 6mm 8mm 8mm 8mm;
        }}
        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            color: #1e293b;
            line-height: 1.38;
            font-size: 9.4pt;
            margin: 0;
            padding: 0;
            background: #f1f5f9;
        }}
        .page {{
            background: #ffffff;
            width: 210mm;
            min-height: 297mm;
            margin: 0 auto 16px auto;
            padding: 10mm 13mm;
            box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
            page-break-after: always;
            break-after: page;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        @media print {{
            body {{
                background: none;
            }}
            .page {{
                width: 100%;
                min-height: auto;
                margin: 0;
                padding: 0;
                box-shadow: none;
            }}
        }}

        /* 顶部与底部全局条 */
        .page-top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1.5px solid #0f172a;
            padding-bottom: 3px;
            margin-bottom: 8px;
        }}
        .top-tag {{
            font-size: 8.5pt;
            font-weight: 800;
            color: #2563eb;
            letter-spacing: 0.5px;
        }}
        .top-brand {{
            font-size: 8pt;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
        }}
        .page-bottom-bar {{
            display: flex;
            justify-content: space-between;
            font-size: 7.5pt;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 3px;
            margin-top: 6px;
        }}

        /* 封面现代化设计 */
        .cover-page {{
            justify-content: center;
            align-items: center;
            padding: 16mm;
        }}
        .cover-card {{
            width: 100%;
            border: 2px solid #0f172a;
            border-radius: 12px;
            padding: 20mm 16mm;
            text-align: center;
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }}
        .badge-pill {{
            display: inline-block;
            background: #0f172a;
            color: #ffffff;
            font-size: 8.5pt;
            font-weight: 700;
            padding: 4px 14px;
            border-radius: 20px;
            letter-spacing: 1px;
            margin-bottom: 16px;
        }}
        .cover-title {{
            font-size: 21pt;
            font-weight: 900;
            line-height: 1.3;
            color: #0f172a;
            margin: 0 0 10px 0;
            letter-spacing: -0.5px;
        }}
        .text-gradient {{
            color: #2563eb;
        }}
        .cover-desc {{
            font-size: 10.5pt;
            color: #475569;
            margin: 0 0 20px 0;
        }}
        .grid-stats {{
            display: flex;
            justify-content: center;
            gap: 14px;
            margin-bottom: 20px;
        }}
        .stat-box {{
            flex: 1;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px;
        }}
        .stat-num {{
            font-size: 15pt;
            font-weight: 800;
            color: #2563eb;
        }}
        .stat-label {{
            font-size: 7.5pt;
            color: #64748b;
            font-weight: 600;
        }}
        .cover-meta-table {{
            border-top: 1px solid #e2e8f0;
            border-bottom: 1px solid #e2e8f0;
            padding: 12px 0;
            text-align: left;
            margin-bottom: 16px;
        }}
        .meta-row {{
            display: flex;
            margin-bottom: 6px;
            font-size: 8.5pt;
        }}
        .meta-row:last-child {{
            margin-bottom: 0;
        }}
        .meta-th {{
            width: 95px;
            font-weight: 700;
            color: #475569;
        }}
        .meta-td {{
            flex: 1;
            color: #0f172a;
        }}
        .cover-quote {{
            font-size: 8.5pt;
            font-style: italic;
            color: #64748b;
            border-left: 3px solid #2563eb;
            padding-left: 8px;
            text-align: left;
            display: inline-block;
        }}

        /* 卡片头部与元数据 */
        .card-top-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 3px;
            margin-bottom: 6px;
        }}
        .card-badge {{
            background: #2563eb;
            color: #ffffff;
            font-size: 8pt;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 4px;
            margin-right: 6px;
        }}
        .card-src {{
            font-size: 7.5pt;
            color: #64748b;
            font-family: ui-monospace, Menlo, Monaco, monospace;
        }}
        .card-timer {{
            font-size: 7.5pt;
            font-weight: 700;
            color: #b45309;
            background: #fef3c7;
            padding: 2px 8px;
            border-radius: 12px;
        }}
        .card-content-area h1 {{
            font-size: 12.8pt;
            color: #0f172a;
            margin: 0 0 4px 0;
            line-height: 1.25;
            font-weight: 800;
        }}
        .card-meta-bar {{
            display: flex;
            gap: 6px;
            margin-bottom: 4px;
        }}
        .tag-pill {{
            display: inline-flex;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            font-size: 7.2pt;
            overflow: hidden;
        }}
        .tag-k {{
            background: #f1f5f9;
            padding: 1px 5px;
            font-weight: 600;
            color: #475569;
        }}
        .tag-v {{
            background: #ffffff;
            padding: 1px 5px;
            font-weight: 700;
            color: #0f172a;
        }}

        /* 记忆词链 (Memory Anchor Bar) 核心设计 */
        .memory-anchor-bar {{
            background: #0f172a;
            color: #e2e8f0;
            border-radius: 5px;
            padding: 3px 8px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            font-size: 7.8pt;
            gap: 4px;
            flex-wrap: wrap;
        }}
        .anchor-label {{
            color: #38bdf8;
            font-weight: 800;
            margin-right: 2px;
        }}
        .anchor-chip {{
            background: #1e293b;
            border: 1px solid #334155;
            color: #f8fafc;
            padding: 1px 6px;
            border-radius: 3px;
            font-weight: 700;
        }}

        /* 结构化 Callout 容器 (排版紧凑且高对比度) */
        .callout {{
            border-radius: 5px;
            padding: 5px 9px;
            margin-bottom: 4px;
            font-size: 8.8pt;
            line-height: 1.34;
            border: 1px solid #e2e8f0;
            border-left-width: 4px;
        }}
        .callout-label {{
            font-size: 8.2pt;
            font-weight: 800;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .callout-elevator {{
            background: #f0f7ff;
            border-left-color: #2563eb;
            color: #0f172a;
        }}
        .callout-elevator .callout-label {{ color: #1d4ed8; }}
        .callout-deep {{
            background: #f8fafc;
            border-left-color: #475569;
            color: #1e293b;
        }}
        .callout-deep .callout-label {{ color: #0f172a; }}
        .callout-tradeoff {{
            background: #fffbeb;
            border-left-color: #f59e0b;
            color: #451a03;
        }}
        .callout-tradeoff .callout-label {{ color: #b45309; }}
        .callout-questions {{
            background: #faf5ff;
            border-left-color: #8b5cf6;
            color: #3b0764;
        }}
        .callout-questions .callout-label {{ color: #6d28d9; }}
        .callout-check {{
            background: #f0fdf4;
            border: 1.2px dashed #16a34a;
            border-left: 4px solid #16a34a;
            color: #14532d;
            padding: 4px 8px;
        }}
        .callout-check .callout-label {{ color: #15803d; }}

        .callout p {{ margin: 1px 0 3px 0; }}
        .callout ul, .callout ol {{ margin: 1px 0 2px 0; padding-left: 15px; }}
        .callout li {{ margin-bottom: 1.5px; }}

        /* 高频追问 Q&A 分层样式 */
        .callout-questions ul, .callout-questions ol {{
            list-style: none !important;
            padding-left: 0 !important;
            margin: 2px 0 !important;
        }}
        .callout-questions li.qa-question {{
            font-weight: 700;
            color: #4c1d95;
            margin-top: 4px;
            margin-bottom: 2px;
            display: flex;
            align-items: baseline;
            gap: 4px;
            list-style: none !important;
        }}
        .callout-questions li.qa-question::before {{
            content: "❓";
            font-size: 7.5pt;
            flex-shrink: 0;
        }}
        .callout-questions li.qa-answer {{
            margin-left: 14px;
            margin-bottom: 3px;
            padding: 2px 6px;
            background: rgba(255, 255, 255, 0.7);
            border-left: 2.5px solid #a855f7;
            border-radius: 0 4px 4px 0;
            color: #1e293b;
            font-size: 8.5pt;
            list-style: none !important;
        }}
        .callout-questions li.qa-sub {{
            margin-left: 26px;
            margin-bottom: 1px;
            color: #334155;
            font-size: 8.3pt;
            list-style-type: disc !important;
        }}

        /* 90秒自测项紧凑无原点样式 */
        .callout-check ul {{
            list-style: none !important;
            padding-left: 2px !important;
            margin: 2px 0 !important;
        }}
        .callout-check li {{
            margin-bottom: 2.5px;
            display: flex;
            align-items: flex-start;
        }}

        .chk-box {{
            display: inline-block;
            width: 11px;
            height: 11px;
            min-width: 11px;
            border: 1.5px solid #16a34a;
            border-radius: 2px;
            margin-right: 5px;
            margin-top: 2px;
            vertical-align: middle;
            text-align: center;
            line-height: 9px;
            font-size: 7.5px;
            color: #ffffff;
            background: #ffffff;
        }}
        .chk-box.checked {{ background: #16a34a; }}

        .card-bottom-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 7.2pt;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 3px;
            margin-top: 4px;
        }}

        /* SVG 图表美化容器 */
        .diagram-wrapper {{
            margin: 6px 0 10px 0;
            background: #ffffff;
            border: 1.5px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
            text-align: center;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .diagram-title {{
            font-size: 9pt;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }}
        .responsive-svg {{
            width: 100% !important;
            height: auto !important;
            display: block;
            margin: 0 auto;
        }}

        /* 表格样式 */
        .table-container {{ margin: 4px 0 6px 0; }}
        table.card-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8pt;
        }}
        table.card-table th, table.card-table td {{
            border: 1px solid #cbd5e1;
            padding: 3px 5px;
            text-align: left;
        }}
        table.card-table th {{
            background: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
        }}
        table.card-table tr:nth-child(even) {{ background: #fafafa; }}

        /* 代码块优化 */
        .code-container {{
            background: #0f172a;
            border-radius: 5px;
            margin: 3px 0 5px 0;
            overflow: hidden;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .code-header {{
            background: #1e293b;
            padding: 2px 7px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .dot {{ width: 5px; height: 5px; border-radius: 50%; display: inline-block; }}
        .dot.red {{ background: #ef4444; }}
        .dot.yellow {{ background: #f59e0b; }}
        .dot.green {{ background: #10b981; }}
        .code-lang {{
            margin-left: 6px;
            font-size: 6.2pt;
            color: #94a3b8;
            font-family: ui-monospace, Menlo, Monaco, monospace;
            text-transform: uppercase;
        }}
        pre {{
            margin: 0;
            padding: 5px 7px;
            color: #f8fafc;
            font-family: ui-monospace, Menlo, Monaco, monospace;
            font-size: 7.6pt;
            line-height: 1.32;
            overflow-x: auto;
        }}
        code {{
            background: #f1f5f9;
            color: #0f172a;
            padding: 1px 3px;
            border-radius: 3px;
            font-family: ui-monospace, Menlo, Monaco, monospace;
            font-size: 7.8pt;
        }}
        pre code {{ background: none; color: inherit; padding: 0; }}

        table.handwrite-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8.2pt;
        }}
        table.handwrite-table th, table.handwrite-table td {{
            border: 1px solid #94a3b8;
            padding: 5px;
        }}
        table.handwrite-table th {{
            background: #f1f5f9;
            font-weight: 700;
            color: #0f172a;
        }}

        strong {{ color: #0f172a; font-weight: 800; }}
        hr.divider {{ border: none; border-top: 1px solid #e2e8f0; margin: 4px 0; }}
    </style>
</head>
<body>
    {body_content}
</body>
</html>
"""
    return full_html


def find_chrome() -> str:
    """寻找本地可用的 Chrome / Edge 渲染引擎"""
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return ""


def main():
    print("==================================================")
    print(" 开始构建体验优化版面试备战手册 (Interview Prep Handbook)...")
    print("==================================================")

    data = collect_content()
    print(f"[1/3] 扫描知识库就绪：发现 {len(data['cards'])} 张 P0 面试卡片。")

    html_content = build_html(data)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"[2/3] 优化版 HTML 编译成功: {OUTPUT_HTML} ({len(html_content)} 字节)")

    chrome_bin = find_chrome()
    if not chrome_bin:
        print("[!] 未找到 Chrome/Edge 浏览器，已生成独立 HTML，可双击用浏览器打开并按 Command+P 另存为 PDF。")
        return

    print(f"[3/3] 正在通过 Chrome Headless 引擎导出高保真 PDF...")
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUTPUT_PDF}",
        str(OUTPUT_HTML)
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if OUTPUT_PDF.exists():
            size_kb = OUTPUT_PDF.stat().st_size / 1024
            print(f"[√] 极致优化版 PDF 构建成功！")
            print(f"    文件路径: {OUTPUT_PDF}")
            print(f"    文件大小: {size_kb:.1f} KB")
            print("==================================================")
        else:
            print("[x] 未生成 PDF 文件。")
    except Exception as e:
        print(f"[!] Headless 模式调用返回: {e}")
        print(f"    备选方案：你可以直接在浏览器打开 {OUTPUT_HTML}，按 Cmd+P 选择“另存为 PDF”。")

if __name__ == "__main__":
    main()
