"""Simplified version of SLLRunner pipeline using DeepSeek models and Bocha search engine.

This module provides a streamlined implementation focused on:
1. Conversation simulation
2. Question generation
3. Outline generation
4. Article generation
5. Article polishing

Required environment variables:
    - BOCHA_API_KEY： Bocha Search API key
    - ALI_MODEL_API_KEY： Aliyun model API key
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from openai import OpenAI

@dataclass
class SLLConfig:
    """Configuration for SLLRunner system"""
    output_dir: str
    max_conv_turns: int
    max_perspectives: int
    search_top_k: int
    temperature: float
    top_p: float
    model: str

class SLL:
    def __init__(self, config: SLLConfig):
        self.config = config
        self.client = OpenAI(
            api_key=os.getenv("ALI_MODEL_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.logger = logging.getLogger(__name__)

    def search_bocha(self, query: str) -> List[Dict[str, str]]:
        """Execute Bocha search and return results"""
        try:
            url = "https://api.bochaai.com/v1/web-search"
            payload = json.dumps({
                "query": query,
                "summary": True,
                "count": self.config.search_top_k,
                "page": 1
            })
            headers = {
                'Authorization': f'Bearer {os.getenv("BOCHA_API_KEY")}',
                'Content-Type': 'application/json'
            }
            response = requests.post(url, headers=headers, data=payload)
            res = response.json()

            results = []
            if res.get('code') == 200 and 'data' in res:
                web_pages = res['data'].get('webPages', {})
                if 'value' in web_pages:
                    for item in web_pages['value']:
                        results.append({
                            'title': item.get('name', ''),
                            'link': item.get('url', ''),
                            'snippet': item.get('summary', '')
                        })
            return results
        except Exception as e:
            self.logger.error(f"Bocha search error: {str(e)}")
            return []

    def generate_questions(self, topic: str) -> List[str]:
        """Generate relevant questions about the topic"""
        prompt = f"假如你在调研报告领域中是一名专家，我需要你关于{topic}提出{self.config.max_perspectives}个关键问题。"
        prompt += "这些问题应该能够涵盖不同方面，并且足够简介和具体，以便进行深入研究。将结果以1、2、3···的顺序列出，结果不要包含其他内容。"

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
                search_results = self.search_bocha(question)
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
