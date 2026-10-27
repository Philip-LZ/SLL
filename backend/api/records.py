"""Generation record listing."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models import GenerationRecord, User

router = APIRouter()


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
