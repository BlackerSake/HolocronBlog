import re
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import mistune

from app.models.article import Article
from app.models.comment import Comment
from app.models.tag import Tag
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleListItem


_markdown = mistune.create_markdown()


def render_markdown(content: str) -> str:
    """将 Markdown 文本渲染为 HTML"""
    return _markdown(content)


def slugify(text: str) -> str:
    """生成slug, 保留中文, 空格/特殊字符替换为连字符"""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', text).strip('-')
    return text or 'untitled'

async def get_published_article_by_slug(db: AsyncSession, slug: str) -> Article | None:
    """根据 slug 获取一篇已发布的未删除文章，关联加载作者、分类和标签

    Args:
        db: 数据库会话
        slug: 文章唯一标识

    Returns:
        文章对象，若不存在则返回 None
    """
    result = await db.execute(
        select(Article)
        .where(Article.slug == slug,
               Article.is_deleted == False,
               Article.is_published == True)
        .options(
            selectinload(Article.author),
            selectinload(Article.category),
            selectinload(Article.tags),
        )
    )
    return result.scalar_one_or_none()

async def get_article_by_slug(
        db: AsyncSession,
        slug: str,
) -> Article | None:
    """根据 slug 获取一篇未删除文章（不限发布状态），关联加载作者、分类和标签

    Args:
        db: 数据库会话
        slug: 文章唯一标识

    Returns:
        文章对象，若不存在则返回 None
    """
    result = await db.execute(
        select(Article)
        .where(Article.slug == slug, Article.is_deleted == False)
        .options(
            selectinload(Article.author),
            selectinload(Article.category),
            selectinload(Article.tags),
        )
    )
    return result.scalar_one_or_none()


async def resolve_slug_conflict(db: AsyncSession, slug: str, user_id: int) -> str:
    """检查 slug 是否已存在，冲突则追加时间戳后缀以避免重复

    Args:
        db: 数据库会话
        slug: 待检查的 slug 值
        user_id: 当前用户 ID，用于生成唯一后缀

    Returns:
        无冲突的 slug 字符串
    """
    existing = await db.execute(
        select(Article).where(Article.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{user_id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    return slug


async def set_article_tags(db: AsyncSession, article: Article, tag_ids: list[int]) -> None:
    """给文章设置标签关联，替换原有的标签集合

    Args:
        db: 数据库会话
        article: 文章对象
        tag_ids: 标签 ID 列表，为空则不操作
    """
    if not tag_ids:
        return
    tags = (await db.execute(
        select(Tag)
        .where(Tag.id.in_(tag_ids)))).scalars().all()
    article.tags = list(tags)


async def query_articles(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 10,
    category_id: int | None = None,
    tag_id: int | None = None,
    search: str | None = None,
    is_published: bool | None = True,
    author_id: int | None = None,
    is_admin: bool = False,
) -> tuple[list[ArticleListItem], int]:
    """文章列表查询及分页，支持多条件筛选

    根据分类、标签、搜索关键词、发布状态、作者等条件组合筛选，
    管理员模式可额外查看自己未发布的文章。

    Args:
        db: 数据库会话
        page: 页码，从 1 开始
        per_page: 每页条数
        category_id: 按分类筛选
        tag_id: 按标签筛选
        search: 按标题或内容关键词搜索
        is_published: 发布状态筛选，None 表示不限
        author_id: 按作者筛选
        is_admin: 是否为管理员模式（可查看自己的未发布文章）

    Returns:
        (文章列表, 总条数) 的元组
    """
    query = select(Article).where(Article.is_deleted == False)

    if is_published is not None:
        if is_admin and author_id is not None:
            query = query.where(or_(
                Article.is_published == True,
                Article.author_id == author_id,
            ))
        else:
            query = query.where(Article.is_published == is_published)
    elif author_id is not None:
        query = query.where(Article.author_id == author_id)

    if category_id:
        query = query.where(Article.category_id == category_id)
    if tag_id:
        query = query.where(Article.tags.any(Tag.id == tag_id))
    if search:
        query = query.where(or_(
            Article.title.ilike(f"%{search}%"),
            Article.content.ilike(f"%{search}%"),
        ))

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    query = query.order_by(Article.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.options(
        selectinload(Article.author),
        selectinload(Article.category),
        selectinload(Article.tags),
    )

    result = await db.execute(query)
    articles = list(result.scalars().all())
    article_ids = [article.id for article in articles]
    reply_counts = {}
    if article_ids:
        rows = await db.execute(
            select(Comment.article_id, func.count(Comment.id))
            .where(Comment.article_id.in_(article_ids), Comment.is_deleted == False)
            .group_by(Comment.article_id)
        )
        reply_counts = dict(rows.all())

    items = []
    for article in articles:
        article.reply_count = reply_counts.get(article.id, 0)
        items.append(ArticleListItem.model_validate(article))
    return items, total


async def create_article(
    db: AsyncSession,
    article_in: ArticleCreate,
    author_id: int,
) -> Article:
    """创建文章的完整业务流程

    根据标题生成 slug（若冲突自动追加时间戳后缀），
    将 Markdown 内容渲染为 HTML，并关联指定标签。

    Args:
        db: 数据库会话
        article_in: 文章创建请求数据（标题、内容、分类、标签等）
        author_id: 作者用户 ID

    Returns:
        创建成功的文章对象（含自动生成的 slug 和 content_html）
    """
    slug = slugify(article_in.title)
    slug = await resolve_slug_conflict(db, slug, author_id)
    html = render_markdown(article_in.content)

    article = Article(
        title=article_in.title,
        slug=slug,
        content=article_in.content,
        content_html=html,
        cover_image=article_in.cover_image,
        summary=article_in.summary,
        is_published=article_in.is_published,
        author_id=author_id,
        category_id=article_in.category_id,
    )

    if article_in.tags_id:
        await set_article_tags(db, article, article_in.tags_id)

    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


async def update_article(
    db: AsyncSession,
    article: Article,
    article_in: ArticleUpdate,
) -> Article:
    """更新文章的完整业务流程

    仅更新请求中传入的字段，自动重新生成 slug 和 content_html，
    若提供了 tags_id 则替换文章的标签关联。

    Args:
        db: 数据库会话
        article: 待更新的文章对象
        article_in: 文章更新请求数据（仅包含需要更新的字段）

    Returns:
        更新后的文章对象
    """
    update_data = article_in.model_dump(exclude_unset=True, exclude={"tags_id"})
    for key, value in update_data.items():
        setattr(article, key, value)

    if "title" in update_data:
        article.slug = slugify(update_data["title"])
    if "content" in update_data:
        article.content_html = render_markdown(update_data["content"])

    if article_in.tags_id is not None:
        await set_article_tags(db, article, article_in.tags_id)

    article.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return article

