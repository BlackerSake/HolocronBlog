
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserProfileUpdate


async def update_user_profile(db: AsyncSession,
                              user: User,
                              data: UserProfileUpdate) -> User:
    """更新当前用户的个人资料

    仅更新请求中显式传入的非 None 字段，None 字段保持原有值不变。
    支持更新的字段由 UserProfileUpdate 模式定义。

    Args:
        db: 数据库会话
        user: 当前登录用户对象
        data: 个人资料更新数据（仅包含需要修改的字段）

    Returns:
        更新后的用户对象
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
    """获取指定用户的公开个人资料

    用于其他用户查看个人主页时获取基本信息。

    Args:
        db: 数据库会话
        user: 目标用户对象

    Returns:
        用户对象（含公开的个人资料字段）
    """
    return await db.get(User, user.id)