import logging
import re
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import psycopg2
from sqlalchemy import text


class WebKnowledge:
    """知识收集模块，负责从网络搜索和整理相关知识"""

    def __init__(self, search_engine, model, personas, database_engine, max_workers=5):
        self.search_engine = search_engine
        self.model = model
        self.personas = personas
        self.database_engine = database_engine
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.research_lock = Lock()
        self.logger = logging.getLogger(__name__)

    def _process_persona_perspective(self, persona_list: List[str], topic: str, questions_number_for_each_persona: int) -> List[Dict[str, Any]]:
        """处理多个角色对问题的分析"""
        try:
            results = []
            for persona in persona_list:
                prompt = f"""
                目前你的身份为：{persona}。
                现在我想要通过搜索引擎获取有关{topic}相关信息，需要你给出{questions_number_for_each_persona}个我应该搜索的内容。
                
                请注意以下方面，提供您的专业见解，同时也要注意与问题：{topic}的相关性：
                1. 专业视角分析：
                   - 从您的专业领域出发，分析问题的关键点
                   - 指出可能被忽视的重要方面
                
                2. 专业建议和解答：
                   - 基于您的专业知识提供详细答案
                   - 补充相关的专业见解
                
                注意：每个问题一行，注意不要生成其他内容，输出只包括搜索内容。输出的搜索内容应该确保简洁和对{topic}的相关性。
                   """
                response = self.model(prompt)[0]
                questions = [line.strip() for line in response.split('\n') if line.strip()]
                questions = questions[:questions_number_for_each_persona]  # 限制问题数量
                results.append({
                    'persona': persona,
                    'questions': questions
                })
            return results
        except Exception as e:
            self.logger.error(f"处理角色问题时发生错误: {str(e)}")
            return []

    def websearch_all_questions(self, topic: str, questions_number: int = 3):
        try:
            # 获取所有问题的搜索结果
            all_search_results = []

            # 使用线程池并行处理所有角色的问题生成
            with self.research_lock:
                results = self._process_persona_perspective(self.personas, topic, questions_number)

            # 收集所有结果
            for result in results:
                if result and 'questions' in result:
                    cleaned_questions = [q.split('. ', 1)[1] if '. ' in q else q for q in result['questions']]
                    all_search_results.extend(cleaned_questions)

            self.search_engine.search(all_search_results)

        except Exception as e:
            self.logger.error(f"知识整理过程中发生错误: {str(e)}")
            raise

    def run_knowledge_curation(self, topic: str, top_k: int = 5, top_p: int = 3) -> List[dict]:
        """知识整理模块
        输出web_information_list的前top_k个元素

        Args:
            topic: 要研究的主题
            top_k: 从数据库检索的结果数量
            top_p: 返回的结果数量

        Returns:
            包含title、lnk和snippet的字典列表
        """
        try:
            self.websearch_all_questions(topic=topic, questions_number=3)
            web_information_list = self.relevant_web_information(information=topic, top_n=top_k)
            return web_information_list[:top_p]
        except Exception as e:
            self.logger.error(f"知识整理过程中发生错误: {str(e)}")
            return []

    def relevant_web_information(self, information: str, top_n: int = 5) -> List[dict]:
        """获取与主题相关的网络信息

        Args:
            information: 查询文本
            top_n: 返回的结果数量 (默认5)

        Returns:
            包含snippet和lnk的字典列表
        """
        try:
            db_engine = self.database_engine()
            query = "SELECT title, lnk, snippet FROM similarity_search(:query_text, :top_k)"
            params = {'query_text': information, 'top_k': top_n}
            results = db_engine.execute_query(query, params)

            return [
                {'title': row[0], 'lnk': row[1], 'snippet': row[2], }
                for row in results
            ]

        except Exception as e:
            self.logger.error(f"获取相关网络信息时发生错误: {str(e)}")
            return []

    def __del__(self):
        """确保线程池正确关闭"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=True)

# if __name__ == '__main__':
#     from backend.SLL_longtext.search import BochaSearch
#     from backend.SLL_longtext.modules.persona_generator import PersonaGenerator
#     from backend.SLL_longtext.models import DeepSeekModel
#     from backend.SLL_longtext.engine import SLLDatabaseEngine
#     topic = "LLM为什么能实现回答用户的问题"
#     search_engine=BochaSearch(bocha_search_api="<your_bocha_api_key>", database_engine=SLLDatabaseEngine)
#     model = DeepSeekModel(api_key="<your_deepseek_api_key>")
#     persona_generator = PersonaGenerator(model=model, topic=topic, max_num_persona=3)
#     webKnowledge = WebKnowledge(search_engine=search_engine, persona_generator=persona_generator,model=model, database_engine=SLLDatabaseEngine)
#     # print(webKnowledge.websearch_all_questions(topic=topic,questions_number=1))
#     print(webKnowledge.relevant_web_information(information="python", top_k=5))