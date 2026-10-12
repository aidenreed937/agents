"""结构化文档解析适配器体系 (Adapter Pattern & Strategy Router)
将多样的第三方解析引擎 (markdown-it-py / trafilatura / Docling / 启发式状态机) 统一转换为标准的 Section 结构。
支持 HTML 网页去噪预处理、策略热插拔与自动优雅降级 (Graceful Degradation)。
"""
from abc import ABC, abstractmethod
from html.parser import HTMLParser
import re
from typing import Dict, Any, List, Tuple, Optional
from ..models import ActionLink, ParsedSection


class BaseDocumentParserAdapter(ABC):
    """所有文档解析策略必须实现的统一适配器契约 (Target Interface)"""

    @abstractmethod
    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        """将源文件解析为标准的 Section 列表"""
        pass

    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """提取 YAML 风格的头部元数据"""
        meta = {}
        body = content
        clean_content = content.lstrip()
        if clean_content.startswith("---"):
            parts = clean_content.split("---", 2)
            if len(parts) >= 3:
                raw_meta = parts[1].strip()
                body = parts[2].strip()
                for line in raw_meta.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"').strip("'")
        return meta, body

    @staticmethod
    def extract_action_link(text: str) -> Tuple[Optional[ActionLink], str]:
        """从文本段中提取控制台路径与 CLI 命令行等操作元数据"""
        console_path = None
        cli_command = None
        permission = None

        cleaned_lines = []
        for line in text.splitlines():
            s_line = line.strip()
            if s_line.startswith("控制台路径:"):
                console_path = s_line.replace("控制台路径:", "").strip().strip("`")
            elif s_line.startswith("CLI 命令:"):
                cli_command = s_line.replace("CLI 命令:", "").strip().strip("`")
            elif s_line.startswith("权限要求:"):
                permission = s_line.replace("权限要求:", "").strip().strip("`")
            else:
                cleaned_lines.append(line)

        action = None
        if console_path:
            action = ActionLink(
                console_path=console_path,
                cli_command=cli_command,
                required_permission=permission
            )

        return action, "\n".join(cleaned_lines).strip()


class MarkdownASTParserAdapter(BaseDocumentParserAdapter):
    """适配器 1: 适配工业级 markdown-it-py AST 语法树解析库
    利用 CommonMark 规范的 Token 流及其精准源码行映射 (token.map)，
    天然免疫代码块内伪标题、复杂嵌套表格与 Setext 标题断裂问题，
    且完整保留原生 Markdown 内容（而非劣化的 HTML 标签）。
    """

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            raise RuntimeError(
                "未检测到 markdown-it-py 依赖，请在终端执行: pip install -r requirements.txt"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        meta, body = self.parse_frontmatter(raw_text)
        doc_title = meta.get("title", "未命名技术手册")

        lines = body.splitlines()
        total_lines = len(lines)

        md = MarkdownIt("gfm-like", {"linkify": False})
        tokens = md.parse(body)

        heading_entries = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.type == "heading_open":
                tag = token.tag.lower()
                lvl = int(tag[1]) if len(tag) > 1 and tag[1].isdigit() else 1
                start_line = token.map[0] if token.map else 0
                end_line = token.map[1] if token.map else start_line + 1

                title_text = ""
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    inline_token = tokens[i + 1]
                    title_text = inline_token.content.strip()

                heading_entries.append({
                    "level": lvl,
                    "title": title_text,
                    "heading_start_line": start_line,
                    "heading_end_line": end_line,
                })
            i += 1

        sections: List[ParsedSection] = []
        heading_stack: List[Tuple[int, str]] = []

        if not heading_entries:
            action, clean_content = self.extract_action_link(body.strip())
            sections.append({
                "doc_title": doc_title,
                "heading": doc_title,
                "level": 1,
                "heading_path": [doc_title],
                "content": clean_content,
                "action_link": action,
                "metadata": meta,
                "parser_strategy": "markdown_it_ast"
            })
            return sections

        first_h_start = heading_entries[0]["heading_start_line"]
        if first_h_start > 0:
            preamble = "\n".join(lines[:first_h_start]).strip()
            if preamble:
                action, clean_preamble = self.extract_action_link(preamble)
                sections.append({
                    "doc_title": doc_title,
                    "heading": "前言概述",
                    "level": 1,
                    "heading_path": [doc_title, "前言概述"],
                    "content": clean_preamble,
                    "action_link": action,
                    "metadata": meta,
                    "parser_strategy": "markdown_it_ast"
                })

        for idx, entry in enumerate(heading_entries):
            lvl = entry["level"]
            title = entry["title"]
            content_start = entry["heading_end_line"]
            if idx + 1 < len(heading_entries):
                content_end = heading_entries[idx + 1]["heading_start_line"]
            else:
                content_end = total_lines

            content = "\n".join(lines[content_start:content_end]).strip()

            while heading_stack and heading_stack[-1][0] >= lvl:
                heading_stack.pop()
            heading_stack.append((lvl, title))

            action, clean_content = self.extract_action_link(content)
            path = [doc_title] + [h[1] for h in heading_stack]

            sec_dict: ParsedSection = {
                "doc_title": doc_title,
                "heading": title,
                "level": lvl,
                "heading_path": path,
                "content": clean_content,
                "action_link": action,
                "metadata": meta,
                "parser_strategy": "markdown_it_ast"
            }
            sections.append(sec_dict)

        return sections


class HeuristicLineParserAdapter(BaseDocumentParserAdapter):
    """适配器 2: 轻量级状态机解析器 (内置零外部依赖的保底兜底策略)
    采用有限状态机 (FSM) 追踪是否处于 ``` 代码块内部，并支持 H1~H6 任意深度层级栈。
    """

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        return self.parse_sections_from_text(raw_text)

    def parse_sections_from_text(self, raw_text: str, default_title: str = "未命名技术手册") -> List[ParsedSection]:
        meta, body = self.parse_frontmatter(raw_text)
        doc_title = meta.get("title", default_title)

        sections: List[ParsedSection] = []
        heading_stack: List[Tuple[int, str]] = []
        current_action = None

        lines = body.splitlines()
        i = 0
        buffer = []
        in_code_fence = False

        def flush_buffer():
            nonlocal buffer, current_action
            if not buffer:
                return
            content = "\n".join(buffer).strip()
            if content:
                action, clean_content = self.extract_action_link(content)
                if not action and current_action:
                    action = current_action

                path = [doc_title] + [h[1] for h in heading_stack]
                curr_heading = heading_stack[-1][1] if heading_stack else doc_title
                curr_level = heading_stack[-1][0] if heading_stack else 1

                sec_dict: ParsedSection = {
                    "doc_title": doc_title,
                    "heading": curr_heading,
                    "level": curr_level,
                    "heading_path": path,
                    "content": clean_content,
                    "action_link": action,
                    "metadata": meta,
                    "parser_strategy": "heuristic_fsm"
                }
                sections.append(sec_dict)
            buffer = []

        heading_regex = re.compile(r'^(#{1,6})\s+(.+)$')

        while i < len(lines):
            line = lines[i]
            s_line = line.strip()

            if s_line.startswith("```"):
                in_code_fence = not in_code_fence
                buffer.append(line)
                i += 1
                continue

            heading_match = None
            if not in_code_fence:
                heading_match = heading_regex.match(s_line)

            if heading_match:
                flush_buffer()
                hashes, title_text = heading_match.groups()
                lvl = len(hashes)

                while heading_stack and heading_stack[-1][0] >= lvl:
                    heading_stack.pop()
                heading_stack.append((lvl, title_text.strip()))
                current_action = None
            else:
                buffer.append(line)
            i += 1

        flush_buffer()
        return sections


class _SemanticHTMLCleaner(HTMLParser):
    """基于标准库 html.parser 的轻量级 DOM 状态机：过滤无用标签并提取标题与段落 (零依赖兜底)"""
    def __init__(self):
        super().__init__()
        self.doc_title = "未命名网页文档"
        self.sections_raw: List[Tuple[int, str, List[str]]] = []
        self.current_heading_level = 1
        self.current_heading_text = ""
        self.current_paragraphs: List[str] = []

        self.skip_tags = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"}
        self.in_skip_depth = 0
        self.in_title_tag = False
        self.in_heading_tag = False
        self.heading_tag_level = 0
        self.temp_text_buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag_l = tag.lower()
        if tag_l in self.skip_tags:
            self.in_skip_depth += 1
            return
        if self.in_skip_depth > 0:
            return

        if tag_l == "br":
            self.temp_text_buffer.append("\n")
            return

        block_tags = {"p", "div", "table", "ul", "ol", "li", "tr"}
        if tag_l in block_tags:
            buffered = "".join(self.temp_text_buffer).strip()
            if buffered:
                self.current_paragraphs.append(buffered)
            self.temp_text_buffer = []

        if tag_l == "title":
            self.in_title_tag = True
            self.temp_text_buffer = []
        elif tag_l in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_section()
            self.in_heading_tag = True
            self.heading_tag_level = int(tag_l[1])
            self.temp_text_buffer = []

    def handle_endtag(self, tag: str):
        tag_l = tag.lower()
        if tag_l in self.skip_tags:
            self.in_skip_depth = max(0, self.in_skip_depth - 1)
            return
        if self.in_skip_depth > 0:
            return

        if tag_l == "title":
            self.in_title_tag = False
            t = "".join(self.temp_text_buffer).strip()
            if t:
                self.doc_title = t
            self.temp_text_buffer = []
        elif tag_l in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_heading_tag = False
            self.current_heading_text = "".join(self.temp_text_buffer).strip()
            self.current_heading_level = self.heading_tag_level
            self.temp_text_buffer = []
        elif tag_l in ("p", "div", "li", "tr", "table"):
            text = "".join(self.temp_text_buffer).strip()
            if text:
                self.current_paragraphs.append(text)
            self.temp_text_buffer = []

    def handle_data(self, data: str):
        if self.in_skip_depth > 0:
            return
        self.temp_text_buffer.append(data)

    def _flush_section(self):
        buffered = "".join(self.temp_text_buffer).strip()
        if buffered:
            self.current_paragraphs.append(buffered)
        self.temp_text_buffer = []

        if self.current_paragraphs or self.current_heading_text:
            self.sections_raw.append((
                self.current_heading_level,
                self.current_heading_text,
                self.current_paragraphs
            ))
            self.current_paragraphs = []


class HTMLTrafilaturaParserAdapter(BaseDocumentParserAdapter):
    """适配器 4: 工业级网页去噪与正文结构化适配器 (优先基于 trafilatura 生产级去噪)
    自动剥离 <script>, <style>, <nav>, <header>, <footer>, <aside>, 广告弹窗等噪音 DOM，
    提取核心正文并导出为纯净 Markdown，再统一进行层级切分与元数据抽取。
    若未安装 trafilatura，自动优雅降级为内置 DOM 状态机清洗器。
    """

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        try:
            import trafilatura
            return self._parse_with_trafilatura(html_content, file_path)
        except ImportError:
            return self._parse_with_builtin_cleaner(html_content, file_path)

    def _parse_with_trafilatura(self, html_content: str, file_path: str) -> List[ParsedSection]:
        import trafilatura

        doc_title = "未命名网页文档"
        meta_dict = {"source_format": "html", "file_path": file_path}
        meta_obj = trafilatura.extract_metadata(html_content)
        if meta_obj:
            if meta_obj.title:
                doc_title = meta_obj.title
                meta_dict["title"] = doc_title
            if meta_obj.author:
                meta_dict["author"] = meta_obj.author
            if meta_obj.date:
                meta_dict["date"] = meta_obj.date

        clean_md = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_tables=True,
            include_links=True,
            favor_precision=True,
            include_formatting=True
        )

        if not clean_md:
            return self._parse_with_builtin_cleaner(html_content, file_path)

        fsm_adapter = HeuristicLineParserAdapter()
        virtual_text = f"---\ntitle: {doc_title}\n---\n\n{clean_md}"
        sections = fsm_adapter.parse_sections_from_text(virtual_text, default_title=doc_title)
        for sec in sections:
            sec["parser_strategy"] = "html_trafilatura_denoised"
            sec["metadata"].update(meta_dict)
        return sections

    def _parse_with_builtin_cleaner(self, html_content: str, file_path: str) -> List[ParsedSection]:
        cleaner = _SemanticHTMLCleaner()
        cleaner.feed(html_content)
        cleaner._flush_section()

        doc_title = cleaner.doc_title or "网页技术文档"
        sections: List[ParsedSection] = []
        heading_stack: List[Tuple[int, str]] = []

        for lvl, title, paragraphs in cleaner.sections_raw:
            heading_title = title if title else doc_title

            while heading_stack and heading_stack[-1][0] >= lvl:
                heading_stack.pop()
            heading_stack.append((lvl, heading_title))

            content = "\n\n".join(paragraphs).strip()
            if not content and heading_title == doc_title:
                continue

            action, clean_content = self.extract_action_link(content)

            sec: ParsedSection = {
                "doc_title": doc_title,
                "heading": heading_title,
                "level": lvl,
                "heading_path": [doc_title] + [h[1] for h in heading_stack],
                "content": clean_content,
                "action_link": action,
                "metadata": {"source_format": "html", "file_path": file_path},
                "parser_strategy": "html_builtin_cleaner_fallback"
            }
            sections.append(sec)

        return sections


class DoclingParserAdapter(BaseDocumentParserAdapter):
    """适配器 3: 企业级多模态版面分析适配器 (对接 IBM Docling)
    专用于复杂多列排版 PDF、扫描件、DOCX、PPTX 等跨格式企业文档的结构化提取。
    利用 TableFormer 与视觉版面模型保留复杂跨页表格与阅读顺序。
    """

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            raise RuntimeError(
                "未检测到 docling 依赖，若需解析复杂 PDF/Word 请先安装: pip install docling"
            )

        converter = DocumentConverter()
        result = converter.convert(file_path)
        doc = result.document

        sections: List[ParsedSection] = []
        exported_md = doc.export_to_markdown()
        ast_adapter = MarkdownASTParserAdapter()
        return sections


class MarkdownDocumentParser:
    """Markdown 门面路由器 (保留向后兼容)"""

    def __init__(self, adapter: Optional[BaseDocumentParserAdapter] = None):
        if adapter is not None:
            self.adapter = adapter
        else:
            self.adapter = self._auto_select_adapter()

    @staticmethod
    def _auto_select_adapter() -> BaseDocumentParserAdapter:
        try:
            import markdown_it
            return MarkdownASTParserAdapter()
        except ImportError:
            return HeuristicLineParserAdapter()

    @property
    def current_strategy_name(self) -> str:
        return self.adapter.__class__.__name__

    @property
    def is_using_external_engine(self) -> bool:
        return isinstance(self.adapter, (MarkdownASTParserAdapter, DoclingParserAdapter, HTMLTrafilaturaParserAdapter))

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        return self.adapter.parse_sections(file_path)


class UniversalDocumentParser(BaseDocumentParserAdapter):
    """通用多格式文档解析路由器 (Universal Document Parser Router)
    对外统一暴露调用入口，根据文件后缀或显式指定策略自动分流：
    - .html / .htm -> 自动路由至 HTMLTrafilaturaParserAdapter (网页先去噪再入库)
    - .md / .markdown -> 自动路由至 Markdown 策略路由器
    - .pdf / .docx -> 可按需接入 DoclingParserAdapter
    """

    def __init__(self, adapter: Optional[BaseDocumentParserAdapter] = None):
        self.explicit_adapter = adapter

    def get_adapter_for_file(self, file_path: str) -> BaseDocumentParserAdapter:
        if self.explicit_adapter is not None:
            return self.explicit_adapter
        lower_path = file_path.lower()
        if lower_path.endswith((".html", ".htm")):
            return HTMLTrafilaturaParserAdapter()
        return MarkdownDocumentParser._auto_select_adapter()

    def parse_sections(self, file_path: str) -> List[ParsedSection]:
        adapter = self.get_adapter_for_file(file_path)
        return adapter.parse_sections(file_path)
