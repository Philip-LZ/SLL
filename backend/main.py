from fastapi import FastAPI, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import time
import json

from chat_response_processor import ChatResponseProcessor, ChatMessage
from logging_config import setup_logging
from SLL_longtext.config import SLLConfig
from SLL_longtext.engine import SLL, ArticleRequest
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

app = FastAPI(title="SLL Chat API", version="0.0.1")

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

# 定义文章生成请求模型
class ArticleGenerateRequest(BaseModel):
    topic: str
    outline: str
    research_data: List[Dict[str, Any]]

# 初始化SLL配置
sll_config = SLLConfig(
    output_dir="./results",
    max_conv_turns=3,
    max_perspectives=3,
    search_top_k=3,
    temperature=0.7,
    top_p=0.9,
    model="deepseek/deepseek-chat"
)

# 初始化SLL实例
sll = SLL(sll_config)

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

@app.post("/api/generate_outline")
async def generate_outline(request: ArticleRequest):
    try:
        api_logger.info(f"开始生成大纲，主题：{request.topic}")
        result = sll.generate_outline(request.topic)
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        error_msg = f"大纲生成错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

@app.post("/api/generate_article")
async def generate_article(request: ArticleGenerateRequest):
    try:
        api_logger.info(f"开始生成文章，主题：{request.topic}")
        result = sll.generate_article(
            topic=request.topic,
            outline=request.outline,
            research_data=request.research_data
        )
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        error_msg = f"文章生成错误: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

@app.get("/")
async def read_root():
    return {"status": "ok", "message": "SLL Chat API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)