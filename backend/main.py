from fastapi import FastAPI, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import time
import json

from logging_config import setup_logging
from SLL_longtext.engine import SLLRunner, SLLRunnerArguments, SLLConfigs
from typing import List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from router import router as auth_router

# 加载环境变量
load_dotenv()

# 初始化日志系统
loggers = setup_logging()
api_logger = loggers['api']
chat_logger = loggers['chat']
error_logger = loggers['error']

app = FastAPI(title="SLLRunner Chat API", version="0.0.1")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





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

    # 获取请求体内容
    body = b""
    async for chunk in request.stream():
        body += chunk
    request._receive = stream_reset(body)

    # 尝试解析JSON请求体
    try:
        body_content = json.loads(body) if body else "No body content"
    except json.JSONDecodeError:
        body_content = body.decode() if body else "No body content"

    # 记录请求开始信息
    api_logger.info(
        "\n=== Incoming Request ===\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Method: {request.method}\n"
        f"Path: {request.url.path}\n"
        f"Query Params: {dict(request.query_params)}\n"
        f"Headers: {dict(request.headers)}\n"
        f"Body: {body_content}\n"
        "======================"
    )
    print("\n=== Incoming Request ===\n"
          f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
          f"Method: {request.method}\n"
          f"Path: {request.url.path}\n"
          f"Query Params: {dict(request.query_params)}\n"
          f"Headers: {dict(request.headers)}\n"
          f"Body: {body_content}\n"
          "======================")

    response = await call_next(request)
    process_time = time.time() - start_time

    # 记录响应信息
    api_logger.info(
        "\n=== Response Info ===\n"
        f"Status: {response.status_code}\n"
        f"Process Time: {process_time:.2f}s\n"
        "===================="
    )
    print("\n=== Response Info ===\n"
          f"Status: {response.status_code}\n"
          f"Process Time: {process_time:.2f}s\n"
          "====================")

    return response


def stream_reset(body: bytes):
    async def receive():
        return {"type": "http.request", "body": body}

    return receive


app.include_router(auth_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
