"""文章润色器模块，用于优化和润色生成的文章"""
import json


class ArticlePolisher:
    """文章润色器类"""

    def __init__(self, topic: str, draft_article: str, web_information: list[str], model):
        self.topic = topic
        self.web_information = web_information
        self.draft_article = draft_article
        self.model = model

    def generate(self) -> str:
        """润色生成的文章"""
        context = json.dumps(self.web_information, ensure_ascii=False)
        prompt = f"""
        你现在的身份是：专业文章编辑，擅长对文章进行润色和优化，使其更加专业、流畅和引人入胜。

        请对以下关于'{self.topic}'的文章进行润色和优化。

        原文：
        {self.draft_article}

        参考资料：
        {context}

        润色要求：
        1. 保持文章的核心内容和主题不变
        2. 优化语言表达，使其更加流畅自然
        3. 增强文章的专业性和学术性
        4. 改善段落之间的过渡和连接
        5. 确保文章结构清晰，重点突出
        6. 适当补充专业术语和行业词汇
        7. 保持文章的可读性和易理解性
        8. 确保文章的论述更加严谨和准确
        9. 优化文章的开头和结尾部分
        10. 保持原有的参考资料引用格式

        注意：
        - 润色时要保持原文的核心观点和论述
        - 避免过度修改导致失去原文的特色
        - 确保优化后的内容与主题'{self.topic}'高度相关
        - 保持专业性的同时要通俗易懂
        """

        response = self.model(prompt=prompt)
        return response[0].strip()
        