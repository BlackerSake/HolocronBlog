
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserProfileUpdate


async def update_user_profile(db: AsyncSession,
                              user: User,
                              data: UserProfileUpdate) -> User:
    """
    更新当前用户的个人资料
    只更新 data 中非 None 的字段，None 的字段保持不变
    """
    update_data = data.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        return user
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    return user

async def get_user_profile(db: AsyncSession,
                         user: User) -> User:
    """
    获取当前用户的公开资料
    用以其他用户查看主页
    """
    return await db.get(User, user.id)