from typing import Dict, Any, Generator, List
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI
from typing import Optional

# 加载环境变量
load_dotenv()

# 获取API配置
DASHSCOPE_API_KEY = os.getenv("ALI_MODEL_API_KEY")

# 定义请求模型
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None

class ChatResponseProcessor:
    @staticmethod
    def format_message(content: str, message_type: str = "answer") -> Dict[str, Any]:
        """格式化消息内容

        Args:
            content: 消息内容
            message_type: 消息类型，可以是 'reasoning' 或 'answer'

        Returns:
            Dict[str, Any]: 格式化后的消息字典
        """
        return {
            "type": message_type,
            "content": content
        }

    @staticmethod
    def create_sse_message(data: Dict[str, Any]) -> str:
        """创建SSE消息

        Args:
            data: 要发送的数据字典

        Returns:
            str: 格式化的SSE消息
        """
        return f"data: {json.dumps(data)}\n\n"

    @staticmethod
    async def process_chat(message: str, conversation_id: str = None, messages: List[Dict[str, str]] = None) -> Generator[str, None, None]:
        if not DASHSCOPE_API_KEY:
            raise HTTPException(status_code=500, detail="服务器配置错误：缺少API配置")

        try:
            # 初始化OpenAI客户端
            try:
                client = OpenAI(
                    api_key=DASHSCOPE_API_KEY,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
            except Exception as e:
                yield ChatResponseProcessor.create_sse_message({
                    "type": "error",
                    "content": f"初始化客户端失败：{str(e)}"
                })
                return

            try:
                # 创建流式聊天完成请求
                completion = client.chat.completions.create(
                    model="deepseek-r1",
                    messages=messages,
                    stream=True
                )

                # 生成会话ID响应
                if conversation_id:
                    yield ChatResponseProcessor.create_sse_message({
                        "type": "conversation_id",
                        "content": conversation_id
                    })

                # 处理流式响应
                for chunk in completion:
                    if not chunk.choices:
                        continue
                    
                    delta = chunk.choices[0].delta
                    
                    # 处理思考过程
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                        yield ChatResponseProcessor.create_sse_message({
                            "type": "reasoning",
                            "content": delta.reasoning_content
                        })
                    # 处理回答内容
                    elif delta.content:
                        yield ChatResponseProcessor.create_sse_message({
                            "type": "answer",
                            "content": delta.content
                        })

            except Exception as e:
                error_message = str(e)
                yield ChatResponseProcessor.create_sse_message({
                    "type": "error",
                    "content": f"处理请求时发生错误：{error_message}"
                })
                # 发送完成信号，确保流式响应正常结束
                yield ChatResponseProcessor.create_sse_message({"type": "done"})
        except Exception as e:
            error_message = ChatResponseProcessor.format_message(
                f"处理响应时发生错误: {str(e)}",
                "error"
            )
            yield ChatResponseProcessor.create_sse_message(error_message)
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def process_stream_response(model_response: str, conversation_id: str) -> Generator[str, None, None]:
        """处理流式响应

        Args:
            model_response: 模型的原始响应
            conversation_id: 会话ID

        Yields:
            str: SSE格式的消息
        """
        try:
            # 首先发送思考过程
            reasoning = "正在思考您的问题..."
            yield ChatResponseProcessor.create_sse_message(
                ChatResponseProcessor.format_message(reasoning, "reasoning")
            )

            # 发送开始回答的信号
            yield ChatResponseProcessor.create_sse_message({"type": "start_answer"})

            # 发送实际答案
            yield ChatResponseProcessor.create_sse_message(
                ChatResponseProcessor.format_message(model_response)
            )

            # 发送完成信号
            yield ChatResponseProcessor.create_sse_message({
                "type": "done",
                "conversation_id": conversation_id
            })

        except Exception as e:
            error_message = ChatResponseProcessor.format_message(
                f"处理响应时发生错误: {str(e)}",
                "error"
            )
            yield ChatResponseProcessor.create_sse_message(error_message)
            raise HTTPException(status_code=500, detail=str(e))


    @staticmethod
    def create_streaming_response(model_response: str, conversation_id: str) -> StreamingResponse:
        """创建流式响应对象

        Args:
            model_response: 模型的响应内容
            conversation_id: 会话ID

        Returns:
            StreamingResponse: FastAPI的流式响应对象
        """
        return StreamingResponse(
            ChatResponseProcessor.process_stream_response(model_response, conversation_id),
            media_type="text/event-stream"
        )