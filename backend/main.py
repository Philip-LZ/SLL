from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import time
from chat_response_processor import ChatResponseProcessor, ChatMessage
from logging_config import setup_logging

# 初始化日志系统
loggers = setup_logging()
api_logger = loggers['api']
chat_logger = loggers['chat']
error_logger = loggers['error']

app = FastAPI(title="SLL Chat API", version="0.0.1")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
async def read_root():
    return {"status": "ok", "message": "SLL Chat API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)