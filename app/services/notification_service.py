

from sqlalchemy import func, update, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification
from app.models.article import Article


async def create_notification(db: AsyncSession,
                              *,
                              initiator_id: int, # 发起者
                              recipient_id: int, # 接收者
                              type: str,
                              content: str,
                              article_id: int | None = None,
                              comment_id: int | None = None,
                              preview: str | None = None,
                              ) -> Notification | None:
    """
    ## 创建一条通知并写入数据库
    业务触发:
    - 有人评论了你的文章 → type="comment_on_article"
    - 有人回复了你的评论 → type="reply_to_comment"
    自己对自己不产生通知（如自己评论自己的文章），直接返回 None
    """
    # 自己对自己不产生通知
    if initiator_id == recipient_id:
        return None
    notification = Notification(
        initiator_id=initiator_id,
        recipient_id=recipient_id,
        content=content,
        type=type,
        article_id=article_id,
        comment_id=comment_id,
        preview=preview,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification

async def get_notifications_list(db: AsyncSession, 
                                 *, 
                                 page: int = 1,
                                 per_page: int = 20,
                                 user_id: int,) -> tuple[list[Notification], int]:
    """
    获取指定用户的通知列表，分页，按创建时间倒序  
    返回:  
        (通知列表, 总条数) 的**元组** 
        不会触发额外查询
    """
    base_query = select(Notification).where(Notification.recipient_id == user_id)
    total = (await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )).scalar()

    query = (
        select(Notification, Article.slug)
        .outerjoin(Article, Notification.article_id == Article.id)
        .where(Notification.recipient_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    items = []
    for notification, article_slug in result.all():
        notification.article_slug = article_slug
        items.append(notification)

    return items, total

async def get_unread_notifications_count(db: AsyncSession, user_id: int) -> int:
    """
    ## 获取指定用户未读通知数量
    这是轮询的核心接口，前端每 30 秒调一次
    """
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == user_id,
               Notification.is_read == False)
    )
    return count or 0
async def mark_notification_is_read(db: AsyncSession, notification_id: int, user_id: int) -> bool:
    """
    ## 标记通知为已读
    必须校验通知的 recipient_id 等于当前 user_id
    """
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id,
               Notification.recipient_id == user_id)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return False
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return True

async def mark_all_notification_is_read(db: AsyncSession, user_id: int) -> int:
    """
    ## 批量标记所有通知为已读  
    返回:  
        - 被标记的通知数量, 0 表示没有通知被标记
    """
    result = await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.is_read == False,
        )
        .values(is_read=True)
        )
    await db.commit()
    return result.rowcount
