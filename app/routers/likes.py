





from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.like import LikeHistoryOut, LikeStatusOut
from app.services.article_service import get_published_article_by_slug
from app.services.like_service import change_like_status, enrich_like_history_items, get_comment_by_id, get_like_status, get_user_history_likes


router = APIRouter()


@router.post("/articles/{slug}/like", response_model=LikeStatusOut)
async def click_like_or_unlike_article(slug: str,
                                       current_user: User = Depends(get_current_user),
                                       db: AsyncSession = Depends(get_db)):
    """
    ## 点赞/取消点赞 文章
    无需传入参数, 点一下切换点赞状态  
    """
    article = await get_published_article_by_slug(db, slug)

    is_liked = await change_like_status(db, current_user.id, article.id, "article")

    await db.refresh(article)

    return LikeStatusOut(
        target_type="article",
        target_id=article.id,
        is_liked=is_liked,
        like_count=article.like_count
    )

@router.post("/comments/{comment_id}/like", response_model=LikeStatusOut)
async def click_like_or_unlike_comment(comment_id: int,
                                       current_user: User = Depends(get_current_user),
                                       db: AsyncSession = Depends(get_db)):
    """
    ## 点赞/取消点赞 评论
    无需传入参数, 点一下切换点赞状态  
    """
    comment = await get_comment_by_id(db, comment_id)
    is_liked = await change_like_status(db, current_user.id, comment_id, "comment")
    await db.refresh(comment)
    return LikeStatusOut(
        target_type="comment",
        target_id=comment.id,
        is_liked=is_liked,
        like_count=comment.like_count
    )

@router.get("/articles/{slug}/like-status", response_model=LikeStatusOut)
async def article_like_status(slug: str,
                              current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    """
    ## 查询当前用户对文章的点赞状态
    """
    article = await get_published_article_by_slug(db, slug)

    status = await get_like_status(db, current_user.id, article.id, "article", article.like_count)
    return LikeStatusOut(**status)

@router.get("/comments/{comment_id}/like-status", response_model=LikeStatusOut)
async def comment_like_status(comment_id: int,
                              current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    """
    ## 获取当前用户对评论的点赞状态
    """
    comment = await get_comment_by_id(db, comment_id)
    status = await get_like_status(db, current_user.id, comment_id, "comment", comment.like_count)
    return LikeStatusOut(**status)
@router.get("/me/like-history", response_model=list[LikeHistoryOut])
async def get_liked_hisotry(target_type: str | None = None,
                            current_user: User = Depends(get_current_user),
                            page: int = Query(1, ge=1),
                            per_page: int = Query(20, le=50),
                            db: AsyncSession = Depends(get_db)):
    """
    ## 获取我的点赞历史
    """
    if target_type and target_type not in ("article", "comment"):
        return []
    items, total = await get_user_history_likes(db, current_user.id, target_type, page, per_page)
    return await enrich_like_history_items(db, items)

@router.get("/users/{user_id}/like-history", response_model=list[LikeHistoryOut])
async def get_users_liked_history_router(user_id: int,
                                         target_type: str | None = None,
                                         page: int = Query(1, ge=1),
                                         per_page: int = Query(20, le=50),
                                         db: AsyncSession = Depends(get_db)):
    """
    ## 获取指定用户点赞历史
    """
    if target_type and target_type not in ("article", "comment"):
        return []
    items, total = await get_user_history_likes(db, user_id, target_type, page, per_page)
    return await enrich_like_history_items(db, items)
