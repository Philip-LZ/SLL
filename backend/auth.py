from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean
from datetime import datetime
from database import Base, get_db
from pydantic import BaseModel
from datetime import timedelta
from sqlalchemy.orm import selectinload

import jwt
from typing import Optional
import os

# 创建路由器
router = APIRouter()

# 用户注册请求模型
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# 创建密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

# 登录请求模型
class UserLogin(BaseModel):
    email: str
    password: str

# JWT配置
if not os.getenv("JWT_SECRET_KEY"):
    raise ValueError("Missing JWT_SECRET_KEY environment variable")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/api/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        # 使用索引优化查询
        # 使用email唯一索引查询
        db_user = db.query(User).filter(
            User.email == user.email
        ).first()
        
        # 用户不存在的处理
        if not db_user:
            raise HTTPException(
                status_code=401,
                detail="邮箱或密码错误"
            )
            
        # 密码验证
        try:
            is_valid = User.verify_password(user.password, db_user.password_hash)
            if not is_valid:
                raise HTTPException(
                    status_code=401,
                    detail="邮箱或密码错误"
                )
        except ValueError as e:  # 捕获密码验证的特定异常
            raise HTTPException(
                status_code=500,
                detail="密码验证过程发生错误"
            )
        
        # 检查用户状态
        if not db_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="账户已被禁用，请联系管理员"
            )
        
        # 创建访问令牌
        try:
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": db_user.email,
                    "user_id": str(db_user.user_id),  # 转换为字符串避免序列化问题
                    "username": db_user.username
                },
                expires_delta=access_token_expires
            )
            
            return {
                "token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": db_user.user_id,
                    "username": db_user.username,
                    "email": db_user.email,
                    "is_active": db_user.is_active
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