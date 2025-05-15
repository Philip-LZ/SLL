from typing import Dict, Any, List
from fastapi import HTTPException
from pydantic import BaseModel
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 获取API配置
DASHSCOPE_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 定义请求模型
class ChatMessage(BaseModel):
    message: str

class ChatResponseProcessor:
    @staticmethod
    async def process_chat(conversation_id: str = None, messages: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """处理聊天请求并返回完整响应

        Args:
            conversation_id: 会话ID
            messages: 历史消息列表

        Returns:
            Dict[str, Any]: 包含响应内容的字典
        """
        if not DASHSCOPE_API_KEY:
            raise HTTPException(status_code=500, detail="服务器配置错误：缺少API配置")

        try:
            # 初始化OpenAI客户端
            client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url="https://api.deepseek.com"
            )

            # 创建聊天完成请求
            completion = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False
            )

            # 获取完整响应
            response = completion.choices[0].message.content

            return {
                "status": "success",
                "message": "聊天响应生成成功",
                "data": {
                    "conversation_id": conversation_id,
                    "content": response
                }
            }

        except Exception as e:
            error_message = f"处理聊天请求时发生错误：{str(e)}"
            raise HTTPException(status_code=500, detail=error_message)