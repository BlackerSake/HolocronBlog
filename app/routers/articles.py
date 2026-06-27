from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.tag import Tag
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleOut, ArticleListItem
from app.schemas.common import Paginated, Response
from app.services.article_service import slugify, render_markdown
from app.core.log import log_call
from app.core.redis import redis_client
import json
router = APIRouter(prefix="/articles", tags=["Articles"])


@log_call
async def _get_article_by_slug(db: AsyncSession, 
                              slug: str,
                              ) -> Article | None:
    """
    ## 根据slug获取一篇未删除文章（不限发布状态）
    查询使用这个接口
    """
    result = await db.execute(
        select(Article).where(Article.slug == slug,
                              Article.is_deleted == False)
        .options(selectinload(Article.author),
        selectinload(Article.category),
        selectinload(Article.tags)),
    )
    return result.scalar_one_or_none()

@router.get("", response_model=Response[Paginated[ArticleListItem]])
@log_call
async def list_articles(
    page: int = Query(1, ge=1), # 默认第一页,最小1
    per_page: int = Query(10, ge=1, le=100), # 默认每页10条,1-100
    category_id: int | None = None,
    tag_id: int | None = None,
    search: str | None = None, #关键词搜索
    db: AsyncSession = Depends(get_db),
):
    """
    # 主页面默认获取列表
    主页面获取列表使用这个接口
    查询等也是这个接口
    """
    query = select(Article).where(Article.is_deleted == False,
                                  Article.is_published == True)
    
    # 筛选条件: 分类, 标签, 关键词
    if category_id:
        query = query.where(Article.category_id == category_id)
    if tag_id:
        query = query.where(Tag.id == tag_id)
    if search:
        query = query.where(or_( # 或条件,且有两个用法
            # Article.title.contains(search), # 大小写敏感
            Article.title.ilike(f"%{search}%"),
            Article.content.ilike(f"%{search}%"), # 模糊匹配, 忽略大小写
        ))
    # 获取符合条件的文章数量
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    #先排序, 再分页
    query = query.order_by(Article.created_at.desc()).offset(
        (page - 1) * per_page).limit(per_page)

    query = query.options(selectinload(Article.author),
                          selectinload(Article.category),
                          selectinload(Article.tags))
    
    result = await db.execute(query) # 执行查询
    articles = result.scalars().all() # 获取结果
    
    items = [ArticleListItem.model_validate(article) for article in articles]
    return Response(data={
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
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
    ## backend 默认获取文章list
    admin 获取自己写的所有文章 ,以及所有已发布文章  
    author 获取自己所有文章  
    后台默认使用这个接口.
    """

    if current_user.role == UserRole.ADMIN.value:
        # 如果是admin
        query = select(Article).where(
            Article.is_deleted == False,
            or_( # 满足任一条件即可 
                # admin & author 获取自己写的所有文章 ,以及所有已发布文章
                Article.is_published == True,
                Article.author_id == current_user.id,
            )
        )
    else: # 如果是 author , 则获取自己所有文章
        query = select(Article).where(
            Article.is_deleted == False,
            Article.author_id == current_user.id
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Article.created_at.desc()).offset(
        (page - 1) * per_page).limit(per_page)
    query = query.options(selectinload(Article.author),
                          selectinload(Article.category),
                          selectinload(Article.tags))

    result = await db.execute(query)
    articles = result.scalars().all()
    items = [ArticleListItem.model_validate(article) for article in articles]
    return Response(data={
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@router.get("/backend/detail/{slug}", response_model=Response[ArticleOut])
@log_call
async def get_backend_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ## 后台用以获取一篇特定文章的内容
    不限发布状态,author 可以检索自己的草稿
    """
    article = await _get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")
    return Response(data=ArticleOut.model_validate(article))


@router.get("/hot",response_model=Response[list[ArticleListItem]])
@log_call
async def get_hot_articles(db: AsyncSession = Depends(get_db)):
    """
    # 获取最火的文章
    1. 优先尝试从redis 读取缓存
    2. 缓存没有命中, 查询数据库
    3. 写入 redis
    """
    cache_key = "hot_articles"

    # 1. 尝试从redis 读取缓存（失败则查 DB）
    try:
        cached_articles = await redis_client.get(cache_key)
        if cached_articles:
            return Response(data=json.loads(cached_articles))
    except Exception:
        pass

    # 2. 缓存没有命中或 Redis 不可用, 查询数据库
    result = await db.execute(
        select(Article).where(
            Article.is_published == True,
            Article.is_deleted == False
        ).order_by(Article.views.desc()).limit(10)
        .options(selectinload(Article.author),
                 selectinload(Article.category),
                 selectinload(Article.tags))
    )
    articles = result.scalars().all()
    items = [ArticleListItem.model_validate(article) for article in articles]

    # 3. 写入 redis（失败不影响返回）
    try:
        await redis_client.set(cache_key, json.dumps([i.model_dump(mode="json") for i in items]), ex=300)
    except Exception:
        pass
    return Response(data=items)

@router.get("/{slug}", response_model=Response[ArticleOut])
@log_call
async def get_article(slug: str, db: AsyncSession = Depends(get_db)):
    """
    ## 获取一篇特定文章的内容
    该文章必须存在且是已发布
    避免草稿泄露
    增加 浏览量计算(redis 原子操作) + 缓存最高浏览量
    """
    article = await _get_article_by_slug(db, slug)
    if not article or not article.is_published: # 防御措施
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    # 浏览量计算 + 1（Redis 不可用时跳过，不影响文章展示）
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
    """
    ## 新建文章,暂定返回状态为不发布
    1. 生成slug
    2. 渲染markdown
    3. 创建 ORM对象
    4. 处理标签关联"""

    # 1. 生成slug
    slug = slugify(article_in.title)
    existing = await db.execute(
        select(Article).where(Article.slug == slug)
    )
    if existing.scalar_one_or_none():
        # 如果标题存在, 就追加用户id 和创建时间 避免冲突
        slug = f"{slug}-{current_user.id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    #TODO 可改进: 为什么不把用户id 和创建时间放在slug中? 或者作为小标题之类的
    # 2. 渲染markdown
    html = render_markdown(article_in.content)

    # 3. 创建 ORM对象
    article = Article(
        title=article_in.title,
        slug=slug,
        content=article_in.content,
        content_html=html,
        cover_image=article_in.cover_image,
        summary=article_in.summary,
        is_published=article_in.is_published,
        author_id=current_user.id,
        category_id=article_in.category_id,
    )
    # 4. 处理标签关联: 如果有标签, 就关联 赋值给 `article.tags`列表
    if article_in.tags_id:
        tags = await db.execute(
            select(Tag).where(Tag.id.in_(article_in.tags_id))
        )
        tags = tags.scalars().all()
        article.tags = list(tags) # 赋值给 `article.tags`列表

    db.add(article)
    await db.commit()
    await db.refresh(article)

    article = await _get_article_by_slug(db, article.slug)
    return Response(data=article)


@router.put("/{slug}", response_model=Response[ArticleOut])
@log_call
async def update_article(
    slug: str,
    article_in: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ## 更新文章, 发布
    1. 获取文章
    2. 检查权限(只允许author更新)
    3. 特殊字段的处理
    4. 更新文章(包括标签关联与更新时间)
    """
    
    # 1. 获取文章
    article = await _get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    # 2. 检查权限(只允许author更新)
    if current_user.id != article.author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足,注: 只有作者本人可修改"
        )

    # 3. 特殊字段的处理
    update_data = article_in.model_dump(exclude_unset=True, exclude={"tags_id"})
    # 标签需要进行 额外查询, 故单独提取
    for key, value in update_data.items():
        setattr(article, key, value) # setattr(对象, 属性名, 属性值)

    # 修改标题时, slug需要重新生成
    if "title" in update_data:
        article.slug = slugify(update_data["title"])
    # 修改内容时, 需要重新渲染markdown
    if "content" in update_data:
        article.content_html = render_markdown(update_data["content"])
    
    # 4. 更新文章(包括标签关联与更新时间)
    if article_in.tags_id is not None:
        tags_result = await db.execute(
            select(Tag).where(Tag.id.in_(article_in.tags_id))
        )
        article.tags = list(tags_result.scalars().all())
        # 传了 tag_ids（即使空列表），则替换当前标签集合
    article.updated_at = datetime.now(timezone.utc)

    await db.commit()
    article = await _get_article_by_slug(db, article.slug)
    return Response(data=article)

@router.patch("/{slug}/unpublish",response_model=Response[ArticleOut])
@log_call
async def unpublish_article(slug: str,
                           db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_admin_user)
                           ):
    """
    ## 取消发布文章
    将文章状态改为草稿（仅限管理员）
    """
    article = await _get_article_by_slug(db, slug)
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
    """删除文章(只有author/admin可删除)
    1. 获取文章
    2. 检查权限(只允许author/admin可删除)
    3. 删除文章
    """
    article = await _get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="文章不存在")

    # 2. 检查权限(只允许author/admin可删除)
    if current_user.id != article.author_id and current_user.role != UserRole.ADMIN.value:
        # 两个条件都不满足, 既不是author, 也不是admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足,注: 只有作者本人或管理员可删除"
        )
    
    # 3. 删除文章
    article.is_deleted = True # 软删除, 不物理删除 
    await db.commit()
    return None
    
