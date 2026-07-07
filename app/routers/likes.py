





from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.like import LikeStatusOut
from app.services.article_service import get_published_article_by_slug
from app.services.like_service import change_like_status, get_like_status


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