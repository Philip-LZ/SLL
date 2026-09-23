"""大纲生成器模块，用于根据研究资料生成文章大纲"""

import json
from typing import List, Dict, Any, Optional, Tuple, Union

from backend.SLL_longtext.utils import ArticleTextProcessing

class OutlineGenerator:
    """大纲生成器，用于生成和改进文章大纲"""
    
    def __init__(self, model, topic: str):
        self.model = model
        self.topic = topic

    def _clean_up_outline(self, outline: str) -> str:
        """清理和格式化大纲文本"""
        return ArticleTextProcessing.clean_up_outline(outline)

    def _improve_outline(self, topic: str, research_data: str) -> str:
        """基于研究资料改进大纲"""
        prompt = f"""
        你现在的身份是：基础事实编写者：专注于全面覆盖主题的基本事实信息。关键词：基础概念，核心要素，客观事实。
        请为主题'{topic}'创建一个详细的文章大纲。
        参考资料：
        {research_data}
        要求：
        1. 使用'#'表示一级标题，'##'表示二级标题，'###'表示三级标题，以此类推
        2. 不要包含其他信息
        3. 不要在大纲中包含主题名称本身
        4. 将一些关键的标题后给出参考资料的title信息，这个标注不用过多，仅在关键且与参考资料信息联系紧密的标题后，但一定要有在标题上的标注。
            示例如下：
            ## LLM的构建（小白学大模型：构建LLM的关键步骤）
        5. 在大纲的最后，仅列出使用的参考资料的title和lnk信息，若没有使用参考资料则不用显示
            示例如下：
            # 参考资料
            - [小白学大模型：构建LLM的关键步骤](https://www.bilibili.com/video/BV1hP411n7xq)
        
        注意：
        二级标题的数量应控制，不宜有过多的二级标题。
        给你的参考资料是为你提供的一系列信息，但文章大纲内容应确保与{topic}的相关性。
        """
        response = self.model(prompt=prompt)
        return self._clean_up_outline(response[0].strip())

    def generate_outline(
        self,
        topic: str,
        research_data: List[str],
    ) -> Union[str, Tuple[str, str]]:
        """生成文章大纲

        Args:
            topic: 文章主题
            research_data: 研究资料列表
            return_draft_outline: 是否返回草稿大纲

        Returns:
            如果return_draft_outline为False，返回最终大纲
            如果return_draft_outline为True，返回(最终大纲, 草稿大纲)的元组
        """
        # 处理研究资料
        research_context = json.dumps(research_data, ensure_ascii=False)

        # 基于研究资料改进大纲
        final_outline = self._improve_outline(topic, research_context)

        return final_outline

# if __name__ == '__main__':
#     from backend.SLL_longtext.search import BochaSearch
#     from backend.SLL_longtext.modules.persona_generator import PersonaGenerator
#     from backend.SLL_longtext.models import DeepSeekModel
#     from backend.SLL_longtext.engine import SLLDatabaseEngine
#     from backend.SLL_longtext.modules.web_knowledge import WebKnowledge
#     topic = "LLM为什么能实现回答用户的问题"
#     search_engine=BochaSearch(bocha_search_api="<your_bocha_api_key>", database_engine=SLLDatabaseEngine)
#     model = DeepSeekModel(api_key="<your_deepseek_api_key>")
#     persona_generator = PersonaGenerator(model=model, topic=topic, max_num_persona=3)
#     webKnowledge = WebKnowledge(search_engine=search_engine, persona_generator=persona_generator,model=model, database_engine=SLLDatabaseEngine)
#     outline_generator = OutlineGenerator(model=model, topic=topic)
#     print(outline_generator.generate_outline(topic=topic,research_data=webKnowledge.run_knowledge_curation(topic=topic)))
#     # print(webKnowledge.websearch_all_questions(topic=topic,questions_number=1))
#     # print(webKnowledge.relevant_web_information(information="python"))