from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.log import log_call
from app.models.user import User
from app.schemas.common import Response
from app.schemas.user import UserProfileUpdate, UserProfileOut

router = APIRouter(tags=["Profile"])


@router.patch("/api/v1/me/profile", response_model=Response[UserProfileOut])
@log_call
async def update_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    修改当前用户的个人资料

    支持部分更新，仅更新传入的字段（PATCH 语义）。

    Args:
        body: 个人资料更新数据（昵称、头像、简介等）
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        Response[UserProfileOut] — 更新后的用户资料
    """
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    await db.commit()
    await db.refresh(current_user)
    return Response(data=UserProfileOut.model_validate(current_user))


@router.get("/api/v1/users/{user_id}/profile", response_model=Response[UserProfileOut])
@log_call
async def view_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    查看用户的公开资料

    根据用户 ID 获取其公开的个人信息，无需登录。

    Args:
        user_id: 目标用户 ID
        db: 数据库会话

    Returns:
        Response[UserProfileOut] — 用户的公开资料

    Raises:
        HTTPException 404: 用户不存在
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return Response(data=UserProfileOut.model_validate(user))
