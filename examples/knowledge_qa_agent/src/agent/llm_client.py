"""工业级大模型客户端体系 (LiteLLM-Driven Universal Client)

基于业界事实标准 LiteLLM，提供对 100+ 模型厂商与云服务的统一支持：
- 覆盖 Anthropic Claude, Google Gemini/Vertex AI, AWS Bedrock, OpenAI, Azure, DeepSeek, SiliconFlow, Ollama 等；
- 统一接口、流式输出、超时控制与跨厂商故障转移 (Fallbacks)；
- 移除多余的中间降级包装与本地模拟层，直接透传真实 API 响应与异常。
"""
import os
import json
import time
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any, List


def load_dotenv_if_exists(custom_path: Optional[str] = None):
    """自动载入 .env 配置文件 (优先使用 python-dotenv 库，缺失时平滑回退至内置轻量解析器)"""
    try:
        from dotenv import load_dotenv, find_dotenv
        if custom_path:
            load_dotenv(custom_path, override=False)
            return
        dotenv_file = find_dotenv(usecwd=True)
        if dotenv_file:
            load_dotenv(dotenv_file, override=False)
            return
    except ImportError:
        pass

    candidate_paths = []
    if custom_path:
        candidate_paths.append(custom_path)

    candidate_paths.extend([
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
    ])

    for p in candidate_paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'").strip('"')
                            if k and k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass


# 模块载入时自动尝试读取本地 .env
load_dotenv_if_exists()


class BaseLLMClient(ABC):
    """大模型客户端统一契约"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """当前使用的模型名称"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """底层驱动提供商标识"""
        pass

    @property
    def is_simulated(self) -> bool:
        """是否处于模拟模式 (始终为 False)"""
        return False

    @property
    def base_url(self) -> str:
        """模型服务接口服务端点 URL"""
        return ""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> str:
        """阻塞式完整生成回答文本"""
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> Iterator[str]:
        """增量流式生成 token 迭代器 (适配 SSE 协议)"""
        pass


class MockLLMClient(BaseLLMClient):
    """用于单元测试与无 litellm 依赖环境的保底客户端"""

    def __init__(self, model_name: str = "mock-model", mock_response: Optional[str] = None):
        self._model_name = model_name
        self._mock_response = mock_response or "根据参考文档分析，故障已确诊 [Doc 1]。"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def is_simulated(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> str:
        return self._mock_response

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> Iterator[str]:
        yield self._mock_response


class LiteLLMClient(BaseLLMClient):
    """工业级多模型统一客户端 (基于 LiteLLM 驱动)
    统一调度 100+ 平台模型，提供统一接口、流式输出、超时控制与跨厂商故障转移 (Fallbacks)。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        fallbacks: Optional[List[str]] = None
    ):
        try:
            import litellm
            self._litellm = litellm
            self._litellm.telemetry = False
            self._litellm.suppress_debug_info = True
        except ImportError:
            raise RuntimeError(
                "未检测到 litellm 依赖。请执行: pip install litellm"
            )

        load_dotenv_if_exists()

        resolved_model = (
            model or
            os.environ.get("LLM_MODEL") or
            os.environ.get("OPENAI_MODEL") or
            os.environ.get("MODEL_NAME") or
            "gpt-4o-mini"
        )
        resolved_key = (
            api_key or
            os.environ.get("LLM_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("ANTHROPIC_API_KEY") or
            os.environ.get("GEMINI_API_KEY") or
            os.environ.get("DEEPSEEK_API_KEY")
        )
        resolved_base = (
            api_base or
            os.environ.get("LLM_BASE_URL") or
            os.environ.get("OPENAI_BASE_URL") or
            os.environ.get("OPENAI_API_BASE")
        )
        if resolved_base and "cloud.siliconflow.cn" in resolved_base:
            resolved_base = resolved_base.replace("cloud.siliconflow.cn", "api.siliconflow.cn")

        self._model = resolved_model
        self.api_key = resolved_key
        self.api_base = resolved_base
        self.timeout = timeout
        self.max_retries = max_retries
        self.fallbacks = fallbacks or []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "litellm_unified"

    @property
    def is_simulated(self) -> bool:
        return False

    @property
    def base_url(self) -> str:
        return self.api_base or "https://api.openai.com/v1"

    def _prepare_kwargs(
        self,
        prompt: str,
        system_prompt: Optional[str],
        stream: bool,
        temperature: float,
        reasoning_effort: Optional[str] = None
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "timeout": self.timeout,
            "num_retries": self.max_retries
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
            has_known_provider = False
            if "/" in self._model:
                prefix = self._model.split("/")[0].lower()
                has_known_provider = prefix in getattr(self._litellm, "provider_list", [])
            if not has_known_provider:
                kwargs["custom_llm_provider"] = "openai"
        if self.fallbacks:
            kwargs["fallbacks"] = self.fallbacks

        effective_effort = reasoning_effort or os.environ.get("LLM_REASONING_EFFORT")
        if effective_effort:
            eff_clean = str(effective_effort).strip().lower()
            if eff_clean in ["none", "off", "disable", "disabled", "false", "0"]:
                if "claude" in self._model.lower() or "anthropic" in self._model.lower():
                    kwargs["thinking"] = {"type": "disabled"}
                else:
                    kwargs["extra_body"] = kwargs.get("extra_body", {})
                    kwargs["extra_body"]["thinking"] = {"type": "disabled"}
            elif eff_clean in ["low", "medium", "high", "xhigh", "max"]:
                kwargs["reasoning_effort"] = eff_clean

        budget_str = os.environ.get("LLM_THINKING_BUDGET")
        if budget_str and budget_str.strip().isdigit():
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": int(budget_str.strip())
            }

        return kwargs

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> str:
        kwargs = self._prepare_kwargs(
            prompt, system_prompt, stream=False, temperature=temperature, reasoning_effort=reasoning_effort
        )
        response = self._litellm.completion(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        if not content and hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
            content = choice.message.reasoning_content
        return content

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None
    ) -> Iterator[str]:
        kwargs = self._prepare_kwargs(
            prompt, system_prompt, stream=True, temperature=temperature, reasoning_effort=reasoning_effort
        )
        response = self._litellm.completion(**kwargs)
        for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None) or ""
                if content:
                    yield content


# 别名导出保证旧调用兼容，统一指向纯净的 LiteLLMClient
UnifiedLLMClient = LiteLLMClient
AutoLLMClient = LiteLLMClient
