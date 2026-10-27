from typing import Dict, Any, List
from fastapi import HTTPException
from pydantic import BaseModel


# 定义请求模型
class LongTextRequest(BaseModel):
    topic: str


class LongTextResponseProcessor:
    def __init__(self, sll_runner: Any = None):
        """初始化LongTextResponseProcessor

        Args:
            sll_runner: SLLRunner实例，用于处理长文生成
        """
        if sll_runner is None:
            raise ValueError("必须提供SLLRunner实例")
        self.sll_runner = sll_runner

    async def process_persona_generation(self, topic: str) -> Dict[str, Any]:
        """处理多视角生成请求并返回完整响应

        Args:
            topic: 文章主题

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        try:
            # 使用SLLRunner生成多个视角
            personas = self.sll_runner.run_persona_generation_module(topic)

            return {
                "status": "success",
                "message": "多视角生成成功",
                "data": {
                    "personas": personas
                }
            }

        except Exception as e:
            error_message = f"处理多视角生成请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    async def process_knowledge_curation(self, topic: str, personas: List[str]) -> Dict[str, Any]:
        """处理知识收集请求并返回完整响应

        Args:
            topic: 文章主题
            personas: 多个视角列表

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        try:
            # 使用SLLRunner收集知识
            web_information = self.sll_runner.run_knowledge_curation_module(topic, personas)

            return {
                "status": "success",
                "message": "知识收集成功",
                "data": {
                    "web_information": web_information
                }
            }

        except Exception as e:
            error_message = f"处理知识收集请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    async def process_outline_generation(self, topic: str, web_information: List[Dict[str, str]] = None) -> Dict[
        str, Any]:
        """处理大纲生成请求并返回完整响应

        Args:
            topic: 文章主题
            web_information: 网络信息列表

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        try:
            # 使用SLLRunner生成大纲
            outline = self.sll_runner.run_outline_generation_module(topic, web_information)

            return {
                "status": "success",
                "message": "大纲生成成功",
                "data": {
                    "outline": outline
                }
            }

        except Exception as e:
            error_message = f"处理大纲生成请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    async def process_article_generation(self, topic: str, outline: str,
                                         web_information: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """处理文章生成请求并返回完整响应

        Args:
            topic: 文章主题
            outline: 文章大纲
            web_information: 网络信息列表

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        try:
            # 使用SLLRunner生成文章
            article = self.sll_runner.run_article_generation_module(topic, outline, web_information)

            return {
                "status": "success",
                "message": "文章生成成功",
                "data": {
                    "article": article
                }
            }

        except Exception as e:
            error_message = f"处理文章生成请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    async def process_article_polish(self, topic: str, article: str, web_information: List[Dict[str, str]] = None) -> \
    Dict[str, Any]:
        """处理文章润色请求并返回完整响应

        Args:
            topic: 文章主题
            article: 原始文章内容
            web_information: 网络信息列表

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        try:
            # 使用SLLRunner润色文章
            polished_article = self.sll_runner.run_article_polishing_module(topic, article, web_information)

            return {
                "status": "success",
                "message": "文章润色成功",
                "data": {
                    "polished_article": polished_article
                }
            }

        except Exception as e:
            error_message = f"处理文章润色请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)
