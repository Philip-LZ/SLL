"""Run with python -m backend.main from the repository root."""

import json
import time
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Load settings before importing routers that configure models and authentication.
load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.api import router
from backend.logging_config import setup_logging

loggers = setup_logging()
api_logger = loggers['api']
app = FastAPI(title="SLLRunner Chat API", version="0.0.1")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
