"""Layer 0: 配置与 Prompt 版本治理层
实现企业级 Prompt 版本控制、变量模板渲染与动态 A/B 测试。
让提示词与业务代码解耦，支持在线热更新与平滑回滚。
"""
from typing import Dict, Any, Optional

class PromptRegistry:
    """提示词版本注册与模板中心"""

    _REGISTRY: Dict[str, Dict[str, str]] = {
        "v1.0": {
            "version": "v1.0",
            "system_prompt": "你是一个企业差旅报销智能体。请从用户输入中提取城市、金额、类别和发票代码。",
            "few_shot_examples": "输入: '上海打车200元' -> 城市: 上海, 金额: 200, 类别: 市内交通费"
        },
        "v1.1": {
            "version": "v1.1",
            "system_prompt": (
                "你是一个高度专业、遵循合规审计的企业差旅报销智能体。"
                "请严格基于事实提取信息，遇到口语别名请保留原词，信息不全时主动声明缺失，严禁凭空臆造发票与行程。"
            ),
            "few_shot_examples": "输入: '魔都打了个滴滴花了350元' -> 原始城市: 魔都, 原始类别: 打了个滴滴, 金额: 350"
        }
    }

    _CURRENT_ACTIVE_VERSION: str = "v1.1"

    @classmethod
    def get_prompt(cls, version: Optional[str] = None) -> Dict[str, str]:
        """获取指定版本的 Prompt，若无则返回当前激活版本"""
        ver = version or cls._CURRENT_ACTIVE_VERSION
        prompt_data = cls._REGISTRY.get(ver)
        if not prompt_data:
            # 优雅降级到 v1.0
            return cls._REGISTRY["v1.0"]
        return prompt_data

    @classmethod
    def get(cls, key: str = "system_prompt", version: Optional[str] = None) -> str:
        """获取指定版本的特定 prompt 字段"""
        data = cls.get_prompt(version)
        return data.get(key, "")

    @classmethod
    def set_active_version(cls, version: str):
        """在线热切换 Prompt 版本"""
        if version in cls._REGISTRY:
            cls._CURRENT_ACTIVE_VERSION = version
        else:
            raise ValueError(f"未知的 Prompt 版本: {version}")
