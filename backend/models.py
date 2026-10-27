"""Database tables shared by API endpoints."""

import uuid
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from backend.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
