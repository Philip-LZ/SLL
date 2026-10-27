"""Login and registration endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.security import ACCESS_TOKEN_EXPIRE_DAYS, create_access_token

router = APIRouter()


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


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
