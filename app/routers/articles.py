from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models.user import User
from app.services.permission_service import if_owner_or_permission
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleOut, ArticleListItem
from app.schemas.common import Paginated, Response
from app.services.article_service import (
    get_article_by_slug, query_articles,
    create_article as svc_create_article,
    update_article as svc_update_article,
)
from app.services.article_cache_service import (
    get_public_article_cached,
    invalidate_article_cache,
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
    """
    获取公开文章列表

    仅返回已发布、未删除的文章，支持分页及按分类、标签、关键词筛选。

    Args:
        page: 页码，从 1 开始
        per_page: 每页数量，默认 10，最大 100
        category_id: 按分类 ID 筛选（可选）
        tag_id: 按标签 ID 筛选（可选）
        search: 关键词搜索（可选，匹配标题）
        db: 数据库会话

    Returns:
        Response[Paginated[ArticleListItem]] — 包含文章列表、总数、页码信息
    """
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
    """
    获取后台文章列表

    管理员可查看所有已发布文章，作者仅查看自己的文章（含草稿）。

    Args:
        page: 页码，从 1 开始
        per_page: 每页数量，默认 50，最大 100
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        Response[Paginated[ArticleListItem]] — 包含文章列表、总数、页码信息
    """
    is_admin = current_user.role_obj.name == "admin"
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
):
    """
    获取后台文章详情

    不限制发布状态，可查看已发布及草稿文章。

    Args:
        slug: 文章 URL 标识
        db: 数据库会话

    Returns:
        Response[ArticleOut] — 文章详情数据

    Raises:
        HTTPException 404: 文章不存在
    """
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")
    return Response(data=ArticleOut.model_validate(article))


@router.get("/hot", response_model=Response[list[ArticleListItem]])
@log_call
async def get_hot_articles(db: AsyncSession = Depends(get_db)):
    """
    获取热门文章排行榜

    按浏览量降序取前 10 篇已发布文章，结果在 Redis 中缓存 5 分钟以减少数据库压力。

    Args:
        db: 数据库会话

    Returns:
        Response[list[ArticleListItem]] — 热门文章列表
    """
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
    """
    获取公开文章详情

    仅返回已发布的文章，同时触发 Redis 浏览量计数 +1。

    Args:
        slug: 文章 URL 标识
        db: 数据库会话

    Returns:
        Response[ArticleOut] — 文章详情数据（含更新后的浏览量）

    Raises:
        HTTPException 404: 文章不存在或未发布
    """
    article = await get_public_article_cached(db, slug)
    if not article:
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
    current_user: User = Depends(require_permission("article:create")),
):
    """
    新建文章

    默认保存为草稿（is_published=False），支持标签关联。需拥有 article:create 权限。

    Args:
        article_in: 文章创建数据（标题、内容、分类、标签等）
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        Response[ArticleOut] — 创建成功的文章数据
    """
    article = await svc_create_article(db, article_in, current_user.id)
    article = await get_article_by_slug(db, article.slug)
    assert article is not None # 使Pylance窄化类型,原返回为 Aticle | None
    await invalidate_article_cache(article.slug)
    return Response(data=article)


@router.put("/{slug}", response_model=Response[ArticleOut])
@log_call
async def update_article(
    slug: str,
    article_in: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("article:update")),
):
    """
    更新文章

    仅作者本人可操作。传入 is_published=true 即可发布文章。

    Args:
        slug: 文章 URL 标识
        article_in: 文章更新数据（支持部分更新）
        db: 数据库会话
        current_user: 当前登录用户（需为文章作者）

    Returns:
        Response[ArticleOut] — 更新后的文章数据

    Raises:
        HTTPException 404: 文章不存在
        HTTPException 403: 非作者尝试修改
    """
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    if current_user.id != article.author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，只有作者本人可修改"
        )

    old_slug = article.slug
    article = await svc_update_article(db, article, article_in)
    article = await get_article_by_slug(db, article.slug)
    assert article is not None
    await invalidate_article_cache(old_slug)
    await invalidate_article_cache(article.slug)
    return Response(data=article)


@router.patch("/{slug}/unpublish", response_model=Response[ArticleOut])
@log_call
async def unpublish_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("article:unpublish")),
):
    """
    取消发布文章

    管理员将已发布文章状态切回草稿。需拥有 article:unpublish 权限。

    Args:
        slug: 文章 URL 标识
        db: 数据库会话
        current_user: 当前登录用户（需为管理员）

    Returns:
        Response[ArticleOut] — 更新后的文章数据

    Raises:
        HTTPException 404: 文章不存在
        HTTPException 400: 文章已是草稿状态
    """
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
    await invalidate_article_cache(slug)
    return Response(data=article)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
@log_call
async def delete_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    软删除文章

    将文章标记为已删除（is_deleted=True），不实际删除记录。仅作者或管理员可操作。

    Args:
        slug: 文章 URL 标识
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        None — 无内容返回（HTTP 204）

    Raises:
        HTTPException 404: 文章不存在
        HTTPException 403: 非作者且非管理员尝试删除
    """
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    if not await if_owner_or_permission(current_user, article.author_id, "article:delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，只有作者本人或管理员可删除"
        )

    article.is_deleted = True
    await db.commit()
    await invalidate_article_cache(slug)
    return None
