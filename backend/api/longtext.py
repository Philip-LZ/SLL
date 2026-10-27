"""Long-form generation and history endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models import ChatHistory, GenerationRecord, User

from backend.services.longtext_response_processor import LongTextRequest, LongTextResponseProcessor
from backend.services.longtext_runner import sll

router = APIRouter()


@router.get("/api/longtext_history/{conversation_id}")
async def get_longtext_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    try:
        # 查询指定的生成记录
        record = (
            db.query(GenerationRecord)
            .filter(
                GenerationRecord.uuid == conversation_id,
                GenerationRecord.user_id == current_user.user_id,
                GenerationRecord.status == 'longtext'
            )
            .options(joinedload(GenerationRecord.chat_history))
            .first()
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail="长文本记录不存在或无权访问"
            )

        # 构建响应数据
        messages = [
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
            "message": "获取长文本记录成功",
            "data": {
                "record": {
                    "uuid": str(record.uuid),
                    "title": record.title,
                    "status": record.status,
                    "created_at": record.created_at.isoformat()
                },
                "messages": messages
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail="获取长文本记录失败，请稍后重试"
        )


@router.post("/api/longtext/generate/{conversation_id}")
async def generate_longtext(conversation_id: uuid.UUID, request: LongTextRequest,
                           current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    try:
        # 验证会话记录是否存在且属于当前用户
        record = db.query(GenerationRecord).filter(
            GenerationRecord.uuid == conversation_id,
            GenerationRecord.user_id == current_user.user_id
        ).first()

        # 如果记录不存在，创建新的生成记录
        if not record:
            record = GenerationRecord(
                uuid=conversation_id,
                user_id=current_user.user_id,
                title=request.topic[:50] + '...' if len(request.topic) > 50 else request.topic,
                status='longtext'
            )
            db.add(record)
            db.commit()
            db.refresh(record)

        # 初始化LongTextResponseProcessor
        processor = LongTextResponseProcessor(sll_runner=sll)

        # 生成多个视角
        personas_response = await processor.process_persona_generation(topic=request.topic)
        personas = personas_response['data']['personas']

        # 收集知识
        web_information_response = await processor.process_knowledge_curation(topic=request.topic, personas=personas)
        web_information = web_information_response['data']['web_information']

        # 生成大纲
        outline_response = await processor.process_outline_generation(
            topic=request.topic,
            web_information=web_information
        )
        outline = outline_response['data']['outline']

        # 保存大纲到聊天历史
        outline_message = ChatHistory(
            record_uuid=conversation_id,
            message_type='assistant',
            content=outline,
            sequence_number=1
        )
        db.add(outline_message)
        db.commit()

        # 生成文章
        article_response = await processor.process_article_generation(
            topic=request.topic,
            outline=outline,
            web_information=web_information
        )

        # 保存文章到聊天历史
        article_message = ChatHistory(
            record_uuid=conversation_id,
            message_type='assistant',
            content=article_response['data']['article'],
            sequence_number=2
        )
        db.add(article_message)
        db.commit()

        return {
            "status": "success",
            "message": "长文本生成成功",
            "data": {
                "outline": outline,
                "article": article_response['data']['article']
            }
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"生成长文本时发生错误：{str(e)}")
