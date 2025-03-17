"""文章润色器模块，用于优化和润色生成的文章"""

from ..llm import LitellmModel

class ArticlePolisher(LitellmModel):
    """文章润色器，继承LitellmModel的基础功能"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def polish(self, article: str) -> str:
        """润色生成的文章"""
        prompt = "请对以下文章进行润色和优化：\n"
        prompt += "要求：\n1. 提升文章的整体表达质量\n2. 确保语言流畅自然\n3. 增加文章的可读性\n4. 添加一个总结性的结论部分\n\n"
        prompt += article

        response = self([{"role": "user", "content": prompt}])
        return response[0].strip()