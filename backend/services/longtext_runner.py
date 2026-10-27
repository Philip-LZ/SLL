"""Model configuration and runner used by the long-form API."""

import os
from pathlib import Path

from backend.SLL_longtext.engine import SLLConfigs, SLLRunner, SLLRunnerArguments
from backend.SLL_longtext.models import DeepSeekModel

# 初始化配置
lm_configs = SLLConfigs()

# 设置DeepSeek模型参数
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("请设置DEEPSEEK_API_KEY环境变量")

# 初始化DeepSeek模型

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
    output_dir=str(Path(__file__).resolve().parents[1] / "results"),
    max_personas=3,
    search_top_k=3,
    retrieve_top_k=8,
    retrieve_top_p=5,
    max_thread_num=10
)

# 初始化SLL运行器
sll = SLLRunner(args=args, lm_configs=lm_configs)
