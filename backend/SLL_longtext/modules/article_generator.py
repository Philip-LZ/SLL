"""文章生成器模块，用于根据大纲和研究数据生成文章"""

import json

class ArticleGenerator:
    """文章生成器类"""
    def __init__(self, topic: str, outline: str, web_information: list[str], model):
        self.topic = topic
        self.web_information = web_information
        self.outline = outline
        self.model = model

    def generate(self) -> str:
        """根据大纲和研究数据生成文章"""
        context = json.dumps(self.web_information, ensure_ascii=False)
        prompt = f"""
        你现在的身份是：专业文章写作者，擅长将研究资料整合成连贯、专业的文章。

        请根据以下大纲，撰写一篇关于'{self.topic}'的文章。

        文章大纲：
        {self.outline}

        参考资料：
        {context}

        写作要求：
        1. 严格按照提供的大纲结构进行写作
        2. 内容要准确、专业且有深度
        3. 语言表达要流畅自然，避免生硬的拼接
        4. 各部分内容要衔接紧密，保持逻辑连贯
        5. 确保文章的整体结构清晰，段落分明
        6. 每个部分都要有充分的展开和论述
        7. 结论部分要有深度的总结和见解
        8. 将一些关键的内容后给出参考资料的title信息，这个标注不用过多，仅在关键且与参考资料信息联系紧密的内容后，但一定要有在文章上的标注。
            示例如下：
            ## LLM的构建（小白学大模型：构建LLM的关键步骤）
        9. 在大纲的最后，仅列出使用的参考资料的title和lnk信息，若没有使用参考资料则不用显示
            示例如下：
            # 参考资料
            - [小白学大模型：构建LLM的关键步骤](https://www.bilibili.com/video/BV1hP411n7xq)

        注意：
        - 生成的文章要确保与主题'{self.topic}'高度相关
        - 保持专业性的同时要通俗易懂
        - 避免重复和冗余的内容
        """

        response = self.model(prompt=prompt)
        return response[0].strip()

# if __name__ == '__main__':
#     from backend.SLL_longtext.search import BochaSearch
#     from backend.SLL_longtext.modules.persona_generator import PersonaGenerator
#     from backend.SLL_longtext.models import DeepSeekModel
#     from backend.SLL_longtext.engine import SLLDatabaseEngine
#     from backend.SLL_longtext.modules.web_knowledge import WebKnowledge
#     from backend.SLL_longtext.modules.outline_generator import OutlineGenerator
#     topic = "LLM为什么能实现回答用户的问题"
#     search_engine=BochaSearch(bocha_search_api="<your_bocha_api_key>", database_engine=SLLDatabaseEngine)
#     model = DeepSeekModel(api_key="<your_deepseek_api_key>")
#     persona_generator = PersonaGenerator(model=model, topic=topic, max_num_persona=3)
#     webKnowledge = WebKnowledge(search_engine=search_engine, persona_generator=persona_generator,model=model, database_engine=SLLDatabaseEngine)
#     outline_generator = OutlineGenerator(model=model, topic=topic)
#     article_generator = ArticleGenerator(topic=topic, web_information=webKnowledge.run_knowledge_curation(topic=topic), outline=outline_generator.generate_outline(topic=topic,research_data=webKnowledge.run_knowledge_curation(topic=topic)),model=model)
#     # print(outline_generator.generate_outline(topic=topic,research_data=webKnowledge.run_knowledge_curation(topic=topic)))
#     # print(webKnowledge.websearch_all_questions(topic=topic,questions_number=1))
#     # print(webKnowledge.relevant_web_information(information="python"))
#     print(article_generator.generate())