




from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserProfileOut, UserProfileUpdate
from app.services.user_service import get_user_profile


router = APIRouter(prefix="", tags=["users"])

@router.patch("/me/profile", response_model=UserProfileOut)
async def update_my_profile(data: UserProfileUpdate,
                            current_user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    """
    更新当前用户的个人资料

    支持部分更新，仅更新传入的字段（PATCH 语义）。

    Args:
        data: 个人资料更新数据
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        UserProfileOut — 更新后的用户资料
    """
    updated = await update_my_profile(db, current_user, data)
    return updated

@router.get("/users/{user_id}/profile", response_model=UserProfileOut)
async def view_user_profile(user_id: int,
                            db: AsyncSession = Depends(get_db)):
    """
    查看用户的公开资料

    根据用户 ID 获取其公开的个人信息，无需登录。

    Args:
        user_id: 目标用户 ID
        db: 数据库会话

    Returns:
        UserProfileOut — 用户的公开资料

    Raises:
        HTTPException 404: 用户不存在
    """
    user = await get_user_profile(db, user_id)
    if user is None:
        raise HTTPException(status_code=404,
                            detail="用户不存在")
    return user