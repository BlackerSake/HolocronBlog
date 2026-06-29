from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models.user import User, UserRole
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleOut, ArticleListItem
from app.schemas.common import Paginated, Response
from app.services.article_service import (
    get_article_by_slug, query_articles,
    create_article as svc_create_article,
    update_article as svc_update_article,
)
from app.core.log import log_call
from app.core.redis import redis_client
import json

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("", response_model=Response[Paginated[ArticleListItem]])
@log_call
async def list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    category_id: int | None = None,
    tag_id: int | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """公开文章列表，仅返回已发布、未删除的文章，支持分页/分类/标签/关键词筛选"""
    items, total = await query_articles(
        db, page=page, per_page=per_page,
        category_id=category_id, tag_id=tag_id, search=search,
        is_published=True,
    )
    return Response(data={
        "items": items, "total": total,
        "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@router.get("/backend/list", response_model=Response[Paginated[ArticleListItem]])
@log_call
async def list_backend_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """后台文章列表，admin 可看所有文章，author 只看自己的文章"""
    is_admin = current_user.role == UserRole.ADMIN.value
    items, total = await query_articles(
        db, page=page, per_page=per_page,
        is_published=True if is_admin else None,
        author_id=current_user.id,
        is_admin=is_admin,
    )
    return Response(data={
        "items": items, "total": total,
        "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@router.get("/backend/detail/{slug}", response_model=Response[ArticleOut])
@log_call
async def get_backend_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """后台文章详情，不限制发布状态，作者可查看自己的草稿"""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")
    return Response(data=ArticleOut.model_validate(article))


@router.get("/hot", response_model=Response[list[ArticleListItem]])
@log_call
async def get_hot_articles(db: AsyncSession = Depends(get_db)):
    """热门文章排行榜，按浏览量降序取前 10，Redis 缓存 5 分钟"""
    cache_key = "hot_articles"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return Response(data=json.loads(cached))
    except Exception:
        pass

    items, _ = await query_articles(
        db, page=1, per_page=10, is_published=True,
    )
    try:
        items_data = [i.model_dump(mode="json") for i in items]
        await redis_client.set(cache_key, json.dumps(items_data), ex=300)
    except Exception:
        pass
    return Response(data=items)


@router.get("/{slug}", response_model=Response[ArticleOut])
@log_call
async def get_article(slug: str, db: AsyncSession = Depends(get_db)):
    """公开文章详情，仅返回已发布文章，同时触发浏览量 +1"""
    article = await get_article_by_slug(db, slug)
    if not article or not article.is_published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    views_key = f"article:views:{slug}"
    try:
        await redis_client.incr(views_key)
        views = await redis_client.get(views_key)
        article.views = int(views or 0)
    except Exception:
        pass

    return Response(data=article)


@router.post("", response_model=Response[ArticleOut])
@log_call
async def create_article(
    article_in: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新建文章，默认存为草稿（is_published=False），支持标签关联"""
    article = await svc_create_article(db, article_in, current_user.id)
    article = await get_article_by_slug(db, article.slug)
    return Response(data=article)


@router.put("/{slug}", response_model=Response[ArticleOut])
@log_call
async def update_article(
    slug: str,
    article_in: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新文章，仅作者可操作；传入 is_published=true 即可发布"""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    if current_user.id != article.author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，只有作者本人可修改"
        )

    article = await svc_update_article(db, article, article_in)
    article = await get_article_by_slug(db, article.slug)
    return Response(data=article)


@router.patch("/{slug}/unpublish", response_model=Response[ArticleOut])
@log_call
async def unpublish_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """管理员取消发布文章，将状态切回草稿"""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该文章不存在",
        )
    if not article.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该文章已经是草稿状态",
        )
    article.is_published = False
    await db.commit()
    return Response(data=article)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
@log_call
async def delete_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除文章，仅作者或管理员可操作"""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    if current_user.id != article.author_id and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，只有作者本人或管理员可删除"
        )

    article.is_deleted = True
    await db.commit()
    return None
