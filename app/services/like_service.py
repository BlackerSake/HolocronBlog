


from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import Article
from app.models.comment import Comment
from app.models.like import Likes


async def _update_target_count(db: AsyncSession,
                             target_id: int, 
                             target_type: str, 
                             delta: int) -> None:
    """
    ## 根据 target_type 更新 对应 like_count
    """
    if target_type == "article":
        await db.execute(
            update(Article)
            .where(Article.id == target_id)
            .values(like_count=Article.like_count + delta)
        )
    elif target_type == "comment":
        await db.execute(
            update(Comment)
            .where(Comment.id == target_id)
            .values(like_count=Comment.like_count + delta)
        )

async def update_like_count(db: AsyncSession,
                            target_id: int, 
                            target_type: str, 
                            delta: int) -> None:
    """
    ## 更新点赞的统一入口
    """
    await _update_target_count(db, target_id, target_type, delta)

async def change_like_status(db: AsyncSession,
                             user_id: int,
                             target_id: int,
                             target_type: str) -> bool:
    """
    ## 切换点赞的状态
    返回 True 表示当前是已赞状态，False 表示未赞状态
    """
    existing = await db.execute(
        select(Likes).where(
            Likes.user_id == user_id,
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
    )
    like = existing.scalar_one_or_none()

    if like:
        await db.delete(like)
        await update_like_count(db, target_id, target_type, -1)
        await db.commit()
        return False
    else:
        like = Likes(
            user_id=user_id,
            target_id=target_id,
            target_type=target_type
        )
        db.add(like)
        await update_like_count(db, target_id, target_type, 1)
        await db.commit()
        return True
    

async def get_like_status(db: AsyncSession,
                          user_id: int,
                          target_id: int,
                          target_type: str,
                          like_count: int) -> dict:
    """
    ## 查询目标的点赞状态
    """
    existing = await db.execute(
        select(Likes.id).where(
            Likes.user_id == user_id,
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
    )
    is_liked = existing.scalar_one_or_none() is not None
    return {
        "target_id": target_id,
        "target_type": target_type,
        "like_count": like_count,
        "is_liked": is_liked,
    }

async def batch_get_like_status(db: AsyncSession,
                                user_id: int,
                                target_ids: list[int],
                                target_type: str) -> dict[int, bool]:
    """
    ## 批量查询目标的点赞状态
    返回 {target_id: True/False} 字典  
    N 个目标只需要 1 次 SQL 查询  
    """
    if not target_ids:
        return {}
    
    result = await db.execute(
        select(Likes.target_id).where(
            Likes.user_id == user_id,
            Likes.target_id.in_(target_ids),
            Likes.target_type == target_type
        )
    )
    like_ids = set(result.scalars().all())
    return {
        target_id: target_id in like_ids
        for target_id in target_ids
    }

async def get_the_likers(db: AsyncSession,
                         target_id: int,
                         target_type: str,
                         limit: int = 10) -> list[Likes]:
    """
    ## 获取目标的点赞者列表
    通用函数, 文章和评论都用同一个
    """
    result = await db.execute(
        select(Likes)
        .where(
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
        .order_by(Likes.create_at.desc())
        .limit(limit)
        )
    return result.scalars().all()