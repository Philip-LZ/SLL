import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Literal, Optional, Union

import dspy
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from backend.SLL_longtext.search import BochaSearch
from backend.SLL_longtext.interface import LMConfigs, Engine
from backend.SLL_longtext.modules import OutlineGenerator, ArticleGenerator, ArticlePolisher, WebKnowledge, PersonaGenerator

load_dotenv()


class SLLConfigs(LMConfigs):
    """SLL不同部分使用的LLM配置。

    鉴于SLL框架中的不同部分具有不同的复杂性，我们使用不同的LLM配置
    以实现质量和效率之间的平衡。如果没有提供特定的配置，使用默认配置
    """

    def __init__(self):
        self.persona_gen_lm = None
        self.webKnowledge_gen_lm = None
        self.outline_gen_lm = None
        self.article_gen_lm = None
        self.article_polish_lm = None

    def init_deepseek_model(
            self,
            deepseek_api_key: str,
            temperature: Optional[float] = 1.2,
            top_p: Optional[float] = 0.9,
    ):
        deepseek_kwargs = {
            "api_key": deepseek_api_key,
            "temperature": temperature,
            "top_p": top_p,
            "api_base": None,
        }

    def set_persona_gen_lm(self, model: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        self.persona_gen_lm = model

    def set_webKnowledge_gen_lm(self, model: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        self.webKnowledge_gen_lm = model

    def set_outline_gen_lm(self, model: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        self.outline_gen_lm = model

    def set_article_gen_lm(self, model: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        self.article_gen_lm = model

    def set_article_polish_lm(self, model: Union[dspy.dsp.LM, dspy.dsp.HFModel]):
        self.article_polish_lm = model


@dataclass
class SLLRunnerArguments:
    """Arguments for controlling the STORM Wiki pipeline."""

    output_dir: str = field(
        metadata={"help": "Output directory for the results."},
    )
    max_personas: int = field(
        default=3,
        metadata={
            "help": "Maximum number of perspectives to consider in perspective-guided question asking."
        },
    )
    search_top_k: int = field(
        default=3,
        metadata={"help": "Top k search results to consider for each search query."},
    )
    retrieve_top_k: int = field(
        default=8,
        metadata={"help": "Top k collected references for each section title."},
    )
    retrieve_top_p: int = field(
        default=5,
        metadata={"help": "Top p for nucleus sampling in the language model."},
    )
    max_thread_num: int = field(
        default=10,
        metadata={
            "help": "Maximum number of threads to use. "
                    "Consider reducing it if keep getting 'Exceed rate limit' error when calling LM API."
        },
    )


class SLLDatabaseEngine:
    """SLL数据库引擎"""

    def __init__(self):
        # 从环境变量获取数据库连接信息
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT')
        self.db_name = os.getenv('DB_NAME')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')

        # 创建数据库连接URL
        self.db_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        self.engine = create_engine(self.db_url)

    def connect(self):
        """建立数据库连接"""
        return self.engine.connect()

    def execute_query(self, query, params=None):
        """执行SQL查询"""
        with self.connect() as connection:
            result = connection.execute(text(query), params)
            return result.fetchall()

    def execute_update(self, query, params=None):
        """执行SQL更新"""
        with self.connect() as connection:
            result = connection.execute(text(query), params)
            connection.commit()
            return result.rowcount


class SLLRunner(Engine):
    """SLL系统实现，使用模块化组件"""

    def __init__(self, args: SLLRunnerArguments, lm_configs: SLLConfigs):
        super().__init__(lm_configs=lm_configs)
        self.args = args
        self.lm_configs = lm_configs

        database_engine = SLLDatabaseEngine()
        self.search_engine = BochaSearch(
            database_engine=database_engine.engine,  # 直接传入 engine 对象
            max_threads=10
        )

        self.persona_gen_lm = self.lm_configs.persona_gen_lm
        self.webKnowledge_gen_lm = self.lm_configs.webKnowledge_gen_lm
        self.outline_gen_lm = self.lm_configs.outline_gen_lm
        self.article_gen_lm = self.lm_configs.article_gen_lm
        self.article_polish_lm = self.lm_configs.article_polish_lm

    def run_persona_generation_module(self, topic: str) -> List[str]:
        """生成多个视角分析主题

        Args:
            topic: 要分析的主题

        Returns:
            不同视角的列表
        """
        persona_generator = PersonaGenerator(
            model=self.persona_gen_lm,
            topic=topic,
            max_num_persona=self.args.max_personas
        )
        return persona_generator.generate_personas()

    def run_knowledge_curation_module(self, topic: str, personas: List) -> List[Dict[str, str]]:
        """收集主题相关的知识

        Args:
            topic: 要研究的主题

        Returns:
            收集到的知识列表，每项包含title、link和snippet
        """
        web_knowledge = WebKnowledge(
            search_engine=self.search_engine,
            personas=personas,
            model=self.webKnowledge_gen_lm,
            database_engine=SLLDatabaseEngine,
            max_workers=self.args.max_thread_num
        )
        return web_knowledge.run_knowledge_curation(
            topic=topic,
            top_k=self.args.retrieve_top_k,
            top_p=self.args.retrieve_top_p
        )

    def run_outline_generation_module(self, topic: str, research_data: List[str]) -> str:
        """生成文章大纲

        Args:
            topic: 文章主题
            research_data: 研究资料

        Returns:
            生成的大纲
        """
        outline_generator = OutlineGenerator(
            model=self.outline_gen_lm,
            topic=topic
        )
        return outline_generator.generate_outline(
            topic=topic,
            research_data=research_data
        )

    def run_article_generation_module(self, topic: str, outline: str, web_information: List[str]) -> str:
        """生成文章内容

        Args:
            topic: 文章主题
            outline: 文章大纲
            web_information: 网络资料

        Returns:
            生成的文章内容
        """
        article_generator = ArticleGenerator(
            topic=topic,
            outline=outline,
            web_information=web_information,
            model=self.article_gen_lm
        )
        return article_generator.generate()

    def run_article_polishing_module(self, topic: str, article: str, web_information: List[str]) -> str:
        """润色文章

        Args:
            topic: 文章主题
            article: 原始文章
            web_information: 网络资料

        Returns:
            润色后的文章
        """
        article_polisher = ArticlePolisher(
            topic=topic,
            model=self.article_polish_lm,
            draft_article=article,
            web_information=web_information,
        )
        return article_polisher.generate()


    def run(self, topic: str) -> Dict[str, Any]:
        """运行SLL系统

        Args:
            topic: 要研究的主题

        Returns:
            包含生成结果的字典，包括：
            - personas: 生成的多个视角
            - web_information: 收集的网络知识
            - outline: 生成的文章大纲
            - article: 生成的文章内容
            - polished_article: 润色后的文章
        """
        # 生成多个视角分析主题
        personas = self.run_persona_generation_module(topic)

        # 收集主题相关的知识
        web_information = self.run_knowledge_curation_module(topic, personas)

        # 生成文章大纲
        outline = self.run_outline_generation_module(topic, web_information)

        # 生成文章内容
        article = self.run_article_generation_module(topic, outline, web_information)

        # 润色文章
        polished_article = self.run_article_polishing_module(topic, article, web_information)

        # 返回所有生成结果
        return {
            "personas": personas,
            "web_information": web_information,
            "outline": outline,
            "article": article,
            "polished_article": polished_article
        }

if __name__ == "__main__":
    # 初始化配置
    lm_configs = SLLConfigs()
    
    # 设置DeepSeek模型参数
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("请设置DEEPSEEK_API_KEY环境变量")
    
    # 初始化DeepSeek模型
    from backend.SLL_longtext.models import DeepSeekModel
    model_kwargs = {
        "api_key": deepseek_api_key,
        "temperature": 1.2,
        "top_p": 0.9
    }
    
    # 为各个模块设置模型
    persona_gen_model = DeepSeekModel(**model_kwargs)
    webKnowledge_gen_model = DeepSeekModel(**model_kwargs)
    outline_gen_model = DeepSeekModel(**model_kwargs)
    article_gen_model = DeepSeekModel(**model_kwargs)
    article_polish_model = DeepSeekModel(**model_kwargs)
    
    lm_configs.set_persona_gen_lm(persona_gen_model)
    lm_configs.set_webKnowledge_gen_lm(webKnowledge_gen_model)
    lm_configs.set_outline_gen_lm(outline_gen_model)
    lm_configs.set_article_gen_lm(article_gen_model)
    lm_configs.set_article_polish_lm(article_polish_model)
    
    # 设置运行参数
    args = SLLRunnerArguments(
        output_dir="./results",
        max_personas=3,
        search_top_k=3,
        retrieve_top_k=8,
        retrieve_top_p=5,
        max_thread_num=10
    )
    
    # 初始化SLL运行器
    runner = SLLRunner(args=args, lm_configs=lm_configs)
    
    # 测试主题
    topic = "为什么南北极有极昼极夜"
    print(f"\n开始处理主题: {topic}")
    
    try:
        # 运行SLL系统
        result = runner.run(topic)
        
        # 打印结果
        print("\n生成结果:")
        print(f"\n1. 多视角分析:")
        for i, persona in enumerate(result['personas'], 1):
            print(f"视角 {i}: {persona}")
            
        print(f"\n2. 收集的网络知识数量: {len(result['web_information'])}")
        
        print(f"\n3. 文章大纲:")
        print(result['outline'])
        
        print(f"\n4. 原始文章长度: {len(result['article'])} 字符")
        print(f"\n5. 润色后文章长度: {len(result['polished_article'])} 字符")
        
    except Exception as e:
        print(f"\n处理过程中出现错误: {str(e)}")
    