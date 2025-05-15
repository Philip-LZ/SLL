import os
import uuid
from datetime import datetime
from datetime import timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, UUID, Integer, ForeignKey, CheckConstraint, \
    Sequence, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Session, relationship, joinedload
from starlette.responses import StreamingResponse

from backend.chat_response_processor import ChatResponseProcessor, ChatMessage
from backend.longtext_response_processor import LongTextResponseProcessor, LongTextRequest
from backend.SLL_longtext.engine import SLLRunner, SLLConfigs, SLLRunnerArguments
from database import Base, get_db

# 创建路由器
router = APIRouter()


class UserLogin(BaseModel):
    email: str
    password: str


# 用户注册请求模型
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


# 创建密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
if not os.getenv("JWT_SECRET_KEY"):
    raise ValueError("Missing JWT_SECRET_KEY environment variable")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7  # 设置访问令牌有效期为7天

security = HTTPBearer()


# 用户模型
class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(60))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """获取密码哈希值"""
        return pwd_context.hash(password)


class GenerationRecord(Base):
    __tablename__ = 'generation_records'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255))
    status = Column(String(20), CheckConstraint("status IN ('chat', 'longtext')"), default='chat')
    created_at = Column(TIMESTAMP, default=lambda: datetime.utcnow())

    chat_history = relationship("ChatHistory", back_populates="record", order_by="ChatHistory.sequence_number")


class ChatHistory(Base):
    __tablename__ = 'chat_history'

    message_id = Column(Integer, primary_key=True)
    record_uuid = Column(UUID(as_uuid=True), ForeignKey('generation_records.uuid', ondelete='CASCADE'),
                         nullable=False)
    message_type = Column(String(10), CheckConstraint("message_type IN ('user', 'assistant')"), nullable=False)
    content = Column(Text, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.utcnow())

    record = relationship("GenerationRecord", back_populates="chat_history")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="令牌已过期",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=401,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                           db: Session = Depends(get_db)):
    """获取当前用户"""
    token = credentials.credentials
    payload = verify_token(token)

    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    return user


@router.post("/api/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        # 使用email唯一索引查询用户
        db_user = db.query(User).filter(User.email == user.email).first()

        # 用户不存在或密码错误
        if not db_user or not User.verify_password(user.password, db_user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="邮箱或密码错误"
            )

        # 检查用户状态
        if not db_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="账户已被禁用，请联系管理员"
            )

        # 创建长期有效的访问令牌
        try:
            access_token = create_access_token(
                data={
                    "sub": db_user.email,
                    "user_id": str(db_user.user_id),
                    "username": db_user.username
                }
            )

            return {
                "status": "success",
                "message": "登录成功",
                "data": {
                    "token": access_token,
                    "token_type": "bearer",
                    "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 过期时间（秒）
                    "user": {
                        "id": db_user.user_id,
                        "username": db_user.username,
                        "email": db_user.email,
                        "is_active": db_user.is_active,
                        "created_at": db_user.created_at.isoformat()
                    }
                }
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="令牌创建过程发生错误"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="登录过程发生错误，请稍后重试"
        )


@router.post("/api/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已被注册")

    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 创建新用户
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=User.get_password_hash(user.password)
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"message": "注册成功", "user": {"username": db_user.username, "email": db_user.email}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="注册失败")


@router.get("/api/generation_records")
async def get_user_records(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 查询当前用户的所有生成记录
        # 使用 subqueryload 和 aliased 实现排序
        records = (
            db.query(GenerationRecord)
            .filter(GenerationRecord.user_id == current_user.user_id)
            .order_by(GenerationRecord.created_at.desc())
            .all()
        )

        return {
            "status": "success",
            "message": "获取历史记录成功",
            "data": records
        }

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail="获取历史记录失败，请稍后重试"
        )


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
