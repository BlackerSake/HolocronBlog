


from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import Article
from app.models.comment import Comment
from app.models.like import Likes
from app.models.user import User


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

async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Comment:
    """
    ## 根据 ID 查询评论
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise ValueError(f"Comment with id {comment_id} not found")
    return comment

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

async def get_user_history_likes(db: AsyncSession,
                                user: int,
                                target_type: str | None = None,
                                page: int = 1,
                                per_page: int = 10) -> tuple[list[Likes], int]:
    """
    ## 查询自己的的点赞历史
    按照时间倒序, 分页返回
    主页展示"我赞过的文章"
    """

    valid_article = and_(
        Likes.target_type == "article",
        exists().where(Article.id == Likes.target_id),
    )
    valid_comment = and_(
        Likes.target_type == "comment",
        exists().where(Comment.id == Likes.target_id),
    )

    query = select(Likes).where(Likes.user_id == user)
    if target_type == "article":
        query = query.where(valid_article)
    elif target_type == "comment":
        query = query.where(valid_comment)
    else:
        query = query.where(or_(valid_article, valid_comment))
    query = query.order_by(Likes.create_at.desc())

    total = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total.scalar()

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()
    return items, total


async def enrich_like_history_items(db: AsyncSession,
                                    items: list[Likes]) -> list[dict]:
    """
    ## 为点赞历史记录补充标题和跳转链接
    返回可直接序列化的 dict 列表
    """
    if not items:
        return []

    article_ids = [item.target_id for item in items if item.target_type == "article"]
    comment_ids = [item.target_id for item in items if item.target_type == "comment"]
    article_map = {}
    comment_map = {}

    if article_ids:
        rows = await db.execute(
            select(Article, User)
            .join(User, Article.author_id == User.id)
            .where(Article.id.in_(article_ids))
        )
        article_map = {article.id: (article, author) for article, author in rows.all()}

    if comment_ids:
        rows = await db.execute(
            select(Comment, Article, User)
            .join(Article, Comment.article_id == Article.id)
            .join(User, Comment.author_id == User.id)
            .where(Comment.id.in_(comment_ids))
        )
        comment_map = {comment.id: (comment, article, author) for comment, article, author in rows.all()}

    result = []
    for item in items:
        base = {
            "liked_at": item.create_at,
            "target_type": item.target_type,
            "target_id": item.target_id,
        }
        if item.target_type == "article":
            row = article_map.get(item.target_id)
            if not row:
                continue
            article, author = row
            author_name = author.nickname or author.username
            result.append({
                **base,
                "title": article.title,
                "url": f"/articles/{article.slug}",
                "article_title": article.title,
                "article_url": f"/articles/{article.slug}",
                "comment_content": "",
                "author_id": author.id,
                "author_name": author_name,
                "author_avatar": author.avatar,
            })
            continue

        row = comment_map.get(item.target_id)
        if not row:
            continue
        comment, article, author = row
        author_name = author.nickname or author.username
        content = "此评论已被删除" if comment.is_deleted else comment.content
        preview = content[:120] + "…" if len(content) > 120 else content
        result.append({
            **base,
            "title": preview,
            "url": f"/articles/{article.slug}#comment-{comment.id}",
            "article_title": article.title,
            "article_url": f"/articles/{article.slug}",
            "comment_content": preview,
            "author_id": author.id,
            "author_name": author_name,
            "author_avatar": author.avatar,
        })
    return result
