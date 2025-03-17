import os
import json
import logging
import requests
import threading
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
from pathlib import Path

import backoff
from dsp import ERRORS, backoff_hdlr, giveup_hdlr
from openai import OpenAI

from .config import SLLConfig
from .search import BochaSearch
from .models import LitellmModel
from .modules import QuestionGenerator, OutlineGenerator, ArticleGenerator, ArticlePolisher

class SLL:
    """SLL系统实现，使用模块化组件"""
    def __init__(self, config: SLLConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.search_engine = BochaSearch(config.search_top_k)
        
        # 初始化各个模块
        model_kwargs = {
            "model": config.model,
            "temperature": config.temperature,
            "top_p": config.top_p
        }
        self.question_generator = QuestionGenerator(max_perspectives=config.max_perspectives, **model_kwargs)
        self.outline_generator = OutlineGenerator(**model_kwargs)
        self.article_generator = ArticleGenerator(**model_kwargs)
        self.article_polisher = ArticlePolisher(**model_kwargs)

    def process_topic(self, topic: str) -> Dict[str, Any]:
        """处理完整的主题生成流程"""
        try:
            # 生成问题
            questions = self.question_generator.generate(topic)
            
            # 研究阶段
            research_data = []
            for question in questions:
                search_results = self.search_engine.search(question)
                research_data.extend(search_results)

            # 生成大纲
            outline = self.outline_generator.generate(topic, research_data)

            # 生成文章
            article = self.article_generator.generate(topic, outline, research_data)

            # 润色文章
            polished_article = self.article_polisher.polish(article)

            # 合并所有模块的token使用情况
            token_usage = {}
            for module in [self.question_generator, self.outline_generator, 
                         self.article_generator, self.article_polisher]:
                usage = module.get_usage_and_reset()
                for model, stats in usage.items():
                    if model not in token_usage:
                        token_usage[model] = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0
                        }
                    token_usage[model]["prompt_tokens"] += stats["prompt_tokens"]
                    token_usage[model]["completion_tokens"] += stats["completion_tokens"]

            return {
                "topic": topic,
                "questions": questions,
                "research_data": research_data,
                "outline": outline,
                "article": article,
                "polished_article": polished_article,
                "token_usage": token_usage
            }

        except Exception as e:
            self.logger.error(f"Error processing topic: {str(e)}")
            raise