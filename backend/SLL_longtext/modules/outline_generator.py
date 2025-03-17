"""大纲生成器模块，用于根据研究资料生成文章大纲"""

import json
from typing import List, Dict, Any
from ..llm import LitellmModel

class OutlineGenerator(LitellmModel):
    """大纲生成器，继承LitellmModel的基础功能"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def generate(self, topic: str, research_data: List[Dict[str, Any]]) -> str:
        """生成文章大纲"""
        context = json.dumps(research_data, ensure_ascii=False)
        prompt = f"请根据关于'{topic}'的研究资料，创建一个详细的文章大纲。要求层次分明，结构合理。"
        prompt += f"研究资料内容如下：{context}"

        response = self([{"role": "user", "content": prompt}])
        return response[0].strip()