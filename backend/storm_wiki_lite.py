"""Simplified version of STORM Wiki pipeline using DeepSeek models and Google search engine.

This module provides a streamlined implementation focused on:
1. Conversation simulation
2. Question generation
3. Outline generation
4. Article generation
5. Article polishing

Required environment variables:
    - DEEPSEEK_API_KEY: DeepSeek API key
    - GOOGLE_API_KEY: Google Search API key
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
from googleapiclient.discovery import build

@dataclass
class StormWikiConfig:
    """Configuration for StormWiki system"""
    output_dir: str = "./results/deepseek"
    max_conv_turns: int = 3
    max_perspectives: int = 3
    search_top_k: int = 3
    temperature: float = 1.0
    top_p: float = 0.9
    model: str = "deepseek-chat"

class StormWikiLite:
    def __init__(self, config: StormWikiConfig):
        self.config = config
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )
        
        # 配置代理
        try:
            from httplib2 import Http, ProxyInfo, socks
            proxy_info = ProxyInfo(
                proxy_type=socks.PROXY_TYPE_HTTP,
                proxy_host="127.0.0.1",
                proxy_port=7890
            )
            http = Http(proxy_info=proxy_info)
        except ImportError:
            self.logger.warning("httplib2未安装，无法使用代理")
            http = None
            
        self.google_service = build(
            "customsearch", "v1",
            developerKey=os.getenv("GOOGLE_API_KEY"),
            http=http
        )
        self.logger = logging.getLogger(__name__)

    def search_google(self, query: str) -> List[Dict[str, str]]:
        """Execute Google search and return results"""
        try:
            results = []
            res = self.google_service.cse().list(
                q=query,
                cx=os.getenv("GOOGLE_CSE_ID"),
                num=self.config.search_top_k
            ).execute()

            if 'items' in res:
                for item in res['items']:
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
            return results
        except Exception as e:
            self.logger.error(f"Google search error: {str(e)}")
            return []

    def generate_questions(self, topic: str) -> List[str]:
        """Generate relevant questions about the topic"""
        prompt = f"假如你在调研报告领域中是一名专家，我需要你关于{topic}提出{self.config.max_perspectives}个关键问题。"
        prompt += "这些问题应该能够涵盖不同方面，并且足够简介和具体，以便进行深入研究。"

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            top_p=self.config.top_p
        )
        
        questions = response.choices[0].message.content.strip().split('\n')
        return [q.strip() for q in questions if q.strip()]

    def generate_outline(self, topic: str, research_data: List[Dict[str, Any]]) -> str:
        """Generate article outline based on research"""
        context = json.dumps(research_data, ensure_ascii=False)
        prompt = f"Based on the research about '{topic}', create a detailed outline. "
        prompt += f"Research context: {context}"

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            top_p=self.config.top_p
        )
        
        return response.choices[0].message.content.strip()

    def generate_article(self, topic: str, outline: str, research_data: List[Dict[str, Any]]) -> str:
        """Generate article based on outline and research"""
        context = json.dumps(research_data, ensure_ascii=False)
        prompt = f"Write an article about '{topic}' following this outline:\n{outline}\n"
        prompt += f"Use this research data: {context}"

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()

    def polish_article(self, article: str) -> str:
        """Polish the generated article"""
        prompt = "Polish this article by improving its flow and adding a summary section:\n"
        prompt += article

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            top_p=self.config.top_p
        )
        
        return response.choices[0].message.content.strip()

    def process_topic(self, topic: str) -> Dict[str, Any]:
        """Process a topic through the complete pipeline"""
        try:
            # Generate questions
            questions = self.generate_questions(topic)
            
            # Research phase
            research_data = []
            for question in questions:
                search_results = self.search_google(question)
                research_data.extend(search_results)

            # Generate outline
            outline = self.generate_outline(topic, research_data)

            # Generate article
            article = self.generate_article(topic, outline, research_data)

            # Polish article
            polished_article = self.polish_article(article)

            return {
                "topic": topic,
                "questions": questions,
                "research_data": research_data,
                "outline": outline,
                "article": article,
                "polished_article": polished_article
            }

        except Exception as e:
            self.logger.error(f"Error processing topic: {str(e)}")
            raise
