"""问题生成器模块，用于生成研究主题相关的关键问题"""

from typing import List
from ..engine import LitellmModel

class QuestionGenerator(LitellmModel):
    """问题生成器，继承LitellmModel的基础功能"""
    def __init__(self, max_perspectives: int, **kwargs):
        super().__init__(**kwargs)
        self.max_perspectives = max_perspectives

    def generate(self, topic: str) -> List[str]:
        """生成关于主题的问题"""
        prompt = (f"假如你在调研报告领域中是一名专家，我需要你关于{topic}提出{self.max_perspectives}个关键问题。"
                  f"这些问题应该能够涵盖不同方面，并且足够简介和具体，以便进行深入研究。将结果以1、2、3···的顺序列出，结果不要包含其他内容。")
        
        try:
            response = self(prompt=prompt)
            if not response:
                raise ValueError("LLM API 返回为空")
            
            # 处理响应...
            return [q.strip() for q in response[0].split('\n') if q.strip()]
        except Exception as e:
            raise RuntimeError(f"生成问题时发生错误: {str(e)}")