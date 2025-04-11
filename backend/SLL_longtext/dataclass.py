"""数据类型定义模块"""

from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ResearchData:
    """研究数据类型"""
    title: str
    content: str
    source: str
    metadata: Dict[str, Any]

@dataclass
class ArticleOutline:
    """文章大纲类型"""
    topic: str
    sections: List[str]
    description: str

@dataclass
class Article:
    """文章类型"""
    topic: str
    content: str
    outline: ArticleOutline
    references: List[ResearchData]

@dataclass
class ResearchQuestion:
    """研究问题类型"""
    topic: str
    questions: List[str]
    perspective: str

