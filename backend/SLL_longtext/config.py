"""SLL系统配置模块"""

from dataclasses import dataclass

@dataclass
class SLLConfig:
    """SLL系统配置"""
    output_dir: str
    max_conv_turns: int
    max_perspectives: int
    search_top_k: int
    temperature: float
    top_p: float
    model: str