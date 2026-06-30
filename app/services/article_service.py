import re
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import mistune

from app.core.config import settings
from app.models.article import Article
from app.models.tag import Tag
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleListItem


_markdown = mistune.create_markdown()


def render_markdown(content: str) -> str:
    return _markdown(content)


def slugify(text: str) -> str:
    """生成slug, 保留中文, 空格/特殊字符替换为连字符"""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', text).strip('-')
    return text or 'untitled'


async def get_article_by_slug(
        db: AsyncSession,
        slug: str,
) -> Article | None:
    """根据slug获取一篇未删除文章（不限发布状态）"""
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
    """检查slug是否已存在，冲突则追加后缀"""
    existing = await db.execute(
        select(Article).where(Article.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{user_id}-{int(datetime.now(settings.tz).timestamp() * 1000)}"
    return slug


async def set_article_tags(db: AsyncSession, article: Article, tag_ids: list[int]) -> None:
    """给文章设置标签关联"""
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
    """文章列表查询+分页，返回 (items, total)"""
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
        query = query.where(Tag.id == tag_id)
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
    items = [ArticleListItem.model_validate(a) for a in result.scalars().all()]
    return items, total


async def create_article(
    db: AsyncSession,
    article_in: ArticleCreate,
    author_id: int,
) -> Article:
    """创建文章的完整业务流程"""
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
    """更新文章的完整业务流程"""
    update_data = article_in.model_dump(exclude_unset=True, exclude={"tags_id"})
    for key, value in update_data.items():
        setattr(article, key, value)

    if "title" in update_data:
        article.slug = slugify(update_data["title"])
    if "content" in update_data:
        article.content_html = render_markdown(update_data["content"])

    if article_in.tags_id is not None:
        await set_article_tags(db, article, article_in.tags_id)

    article.updated_at = datetime.now(settings.tz)
    await db.commit()
    return article




