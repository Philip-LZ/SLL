from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 获取阿里大模型API配置
ALI_MODEL_API_KEY = os.getenv("ALI_MODEL_API_KEY")

# 初始化OpenAI客户端
client = OpenAI(
    api_key=ALI_MODEL_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

app = FastAPI(title="SLL Chat API", version="0.0.1")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义请求模型
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

# 定义响应模型
class ChatResponse(BaseModel):
    response: str
    conversation_id: str

@app.post("/api/chat")
async def chat(message: ChatMessage):
    try:
        # 创建聊天完成请求
        completion = client.chat.completions.create(
            model="deepseek-r1",
            messages=[{"role": "user", "content": message.message}],
            stream=True
        )

        async def generate_response():
            reasoning_content = ""
            answer_content = ""
            is_answering = False

            for chunk in completion:
                if not chunk.choices:
                    if hasattr(chunk, 'usage'):
                        yield f"data: {json.dumps({'type': 'usage', 'content': chunk.usage.__dict__})}\n\n"
                else:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                        reasoning_content += delta.reasoning_content
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta.reasoning_content})}\n\n"
                    elif hasattr(delta, 'content') and delta.content:
                        if not is_answering:
                            is_answering = True
                            yield f"data: {json.dumps({'type': 'start_answer'})}\n\n"
                        answer_content += delta.content
                        yield f"data: {json.dumps({'type': 'answer', 'content': delta.content})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': message.conversation_id or 'new_conversation'})}\n\n"

        return StreamingResponse(generate_response(), media_type="text/event-stream")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API调用失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    return {"status": "ok", "message": "SLL Chat API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)