from fastapi import FastAPI, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import time
import json

from chat_response_processor import ChatResponseProcessor, ChatMessage
from logging_config import setup_logging
from SLL_longtext.engine import SLLRunner, SLLRunnerArguments, SLLConfigs
from typing import List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from auth import router as auth_router

# 加载环境变量
load_dotenv()

# 初始化日志系统
loggers = setup_logging()
api_logger = loggers['api']
chat_logger = loggers['chat']
error_logger = loggers['error']

app = FastAPI(title="SLLRunner Chat API", version="0.0.1")

# 注册认证路由
app.include_router(auth_router)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
sll = SLLRunner(args=args, lm_configs=lm_configs)


# 定义请求模型
class MultiPerspectiveRequest(BaseModel):
    topic: str


class ArticleGenerationRequest(BaseModel):
    topic: str
    outline: str
    web_information: List[Dict[str, str]]


class ArticlePolishRequest(BaseModel):
    topic: str
    article: str
    web_information: List[Dict[str, str]]


@app.get("/")
async def read_root():
    return {"status": "ok", "message": "SLLRunner Chat API is running"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    api_logger.info(
        f"Method: {request.method} Path: {request.url.path} "
        f"Status: {response.status_code} Process Time: {process_time:.2f}s"
    )
    return response


@app.post("/api/chat")
async def chat(message: ChatMessage):
    try:
        chat_logger.info(
            f"New chat request - Message: {message.message[:100]}... "
            f"Conversation ID: {message.conversation_id or 'new_conversation'}"
        )
        return StreamingResponse(
            ChatResponseProcessor.process_chat(
                message=message.message,
                conversation_id=message.conversation_id,
                messages=message.messages
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Chat error: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        raise


@app.post("/api/generate_personas")
async def generate_personas(request: MultiPerspectiveRequest):
    try:
        api_logger.info(f"开始生成多视角分析，主题：{request.topic}")

        # 生成多视角分析
        personas = sll.run_persona_generation_module(request.topic)

        # 收集知识
        web_information = sll.run_knowledge_curation_module(request.topic, personas)

        return JSONResponse(
            status_code=200,
            content={
                "personas": personas,
                "web_information": web_information
            }
        )
    except Exception as e:
        error_msg = f"多视角分析生成错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@app.post("/api/generate_outline_with_research")
async def generate_outline_with_research(request: ArticleGenerationRequest):
    try:
        api_logger.info(f"开始生成大纲，主题：{request.topic}")

        # 生成大纲
        outline = sll.run_outline_generation_module(request.topic, request.web_information)

        return JSONResponse(
            status_code=200,
            content={
                "outline": outline
            }
        )
    except Exception as e:
        error_msg = f"大纲生成错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@app.post("/api/generate_draft_article")
async def generate_draft_article(request: ArticleGenerationRequest):
    try:
        api_logger.info(f"开始生成文章内容，主题：{request.topic}")

        article = sll.run_article_generation_module(
            topic=request.topic,
            outline=request.outline,
            web_information=request.web_information
        )

        return JSONResponse(
            status_code=200,
            content={"article": article}
        )
    except Exception as e:
        error_msg = f"文章内容生成错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@app.post("/api/polish_article")
async def polish_article(request: ArticlePolishRequest):
    try:
        api_logger.info(f"开始润色文章，主题：{request.topic}")

        polished_article = sll.run_article_polishing_module(
            topic=request.topic,
            article=request.article,
            web_information=request.web_information
        )

        return JSONResponse(
            status_code=200,
            content={"polished_article": polished_article}
        )
    except Exception as e:
        error_msg = f"文章润色错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
