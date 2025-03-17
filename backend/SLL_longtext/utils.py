"""通用工具函数模块"""

import json
from typing import List, Dict, Any

def format_research_data(research_data: List[Dict[str, Any]]) -> str:
    """格式化研究数据为字符串"""
    return json.dumps(research_data, ensure_ascii=False)

def format_prompt(base_prompt: str, **kwargs) -> str:
    """格式化提示词"""
    return base_prompt.format(**kwargs)

def parse_list_response(response: str) -> List[str]:
    """解析列表形式的响应"""
    items = response.strip().split('\n')
    return [item.strip() for item in items if item.strip()]