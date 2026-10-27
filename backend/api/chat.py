"""Chat generation and history endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models import ChatHistory, GenerationRecord, User
from sqlalchemy import func

from backend.services.chat_response_processor import ChatMessage, ChatResponseProcessor

router = APIRouter()


@router.get("/api/chat_history/{conversation_id}")
async def get_chat_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    try:
        # 查询指定的生成记录
        record = (
            db.query(GenerationRecord)
            .filter(
                GenerationRecord.uuid == conversation_id,
                GenerationRecord.user_id == current_user.user_id
            )
            .options(joinedload(GenerationRecord.chat_history))
            .first()
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail="对话记录不存在或无权访问"
            )

        # 构建响应数据
        chat_messages = [
            {
                "message_id": msg.message_id,
                "type": msg.message_type,
                "content": msg.content,
                "sequence_number": msg.sequence_number,
                "created_at": msg.created_at.isoformat()
            }
            for msg in record.chat_history
        ]

        return {
            "status": "success",
            "message": "获取对话记录成功",
            "data": {
                "record": {
                    "uuid": str(record.uuid),
                    "title": record.title,
                    "status": record.status,
                    "created_at": record.created_at.isoformat()
                },
                "messages": chat_messages
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail="获取对话记录失败，请稍后重试"
        )


@router.post("/api/chat/{conversation_id}")
async def chat(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db), chat_message: ChatMessage = None):
    try:
        # 验证会话记录是否存在且属于当前用户
        record = db.query(GenerationRecord).filter(
            GenerationRecord.uuid == conversation_id,
            GenerationRecord.user_id == current_user.user_id
        ).first()

        # 如果记录不存在，创建新的对话记录
        if not record:
            record = GenerationRecord(
                uuid=conversation_id,
                user_id=current_user.user_id,
                title=chat_message.message[:50] + '...' if len(chat_message.message) > 50 else chat_message.message,
                status='chat'
            )
            db.add(record)
            db.commit()
            db.refresh(record)

        # 获取当前会话的最大序号
        max_sequence = db.query(func.max(ChatHistory.sequence_number)).filter(
            ChatHistory.record_uuid == conversation_id
        ).scalar() or 0

        # 保存用户消息到数据库
        user_message = ChatHistory(
            record_uuid=conversation_id,
            message_type='user',
            content=chat_message.message,
            sequence_number=max_sequence + 1
        )
        db.add(user_message)
        db.commit()

        # 构建消息历史
        chat_history = db.query(ChatHistory).filter(
            ChatHistory.record_uuid == conversation_id
        ).order_by(ChatHistory.sequence_number).all()

        messages = [{
            "content": msg.content,
            "role": "user" if msg.message_type == "user" else "assistant"
        } for msg in chat_history]

        # 调用AI处理聊天请求
        response = await ChatResponseProcessor.process_chat(
            conversation_id=str(conversation_id),
            messages=messages
        )

        # 保存AI响应到数据库
        assistant_message = ChatHistory(
            record_uuid=conversation_id,
            message_type='assistant',
            content=response['data']['content'],
            sequence_number=max_sequence + 1
        )
        db.add(assistant_message)
        db.commit()

        return response

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"处理聊天请求时发生错误：{str(e)}")
