"""文章生成器模块，用于根据大纲和研究数据生成文章"""

import json
from typing import List, Dict, Any
from ..engine import LitellmModel

class ArticleGenerator(LitellmModel):
    """文章生成器，继承LitellmModel的基础功能"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def generate(self, topic: str, outline: str, research_data: List[Dict[str, Any]]) -> str:
        """根据大纲和研究数据生成文章"""
        context = json.dumps(research_data, ensure_ascii=False)
        prompt = f"请根据以下大纲，撰写一篇关于'{topic}'的文章：\n{outline}\n"
        prompt += f"参考以下研究资料：{context}\n"
        prompt += "要求：\n1. 内容要准确、专业且有深度\n2. 语言表达要流畅自然\n3. 各部分内容要衔接紧密\n4. 适当引用研究资料支持论点"

        response = self(prompt=prompt)
        return response[0].strip()