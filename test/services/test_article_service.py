import pytest
from app.services.article_service import (
    slugify, render_markdown,
    get_article_by_slug, resolve_slug_conflict, set_article_tags,
    query_articles, create_article, update_article,
)
from app.models.article import Article
from app.models.tag import Tag
from app.models.category import Category
from app.schemas.article import ArticleCreate, ArticleUpdate


@pytest.fixture
async def category(db_session):
    cat = Category(name="tech", description="tech")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest.fixture
async def tag(db_session):
    t = Tag(name="python")
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest.fixture
async def article(db_session, test_user, category, tag):
    a = Article(
        title="Original", slug="original",
        content="# Orig", content_html="<h1>Orig</h1>",
        summary="orig summary", is_published=True,
        author_id=test_user.id, category_id=category.id, tags=[tag],
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


class TestSlugify:

    def test_normal_title(self):
        """普通英文标题 -> 小写连字符"""
        assert slugify("Hello World") == "hello-world"

    def test_chinese_title(self):
        """中文标题 -> 保留中文，空格变连字符"""
        assert "-" in slugify("我的 博客 文章")

    def test_special_chars_replaced(self):
        """特殊字符 -> 替换为连字符"""
        assert slugify("Hello, World! #2024") == "hello-world-2024"

    def test_leading_trailing_dashes_removed(self):
        """首尾连字符被去除"""
        assert slugify("--hello--") == "hello"

    def test_empty_after_clean_returns_untitled(self):
        """纯特殊字符 -> 'untitled'"""
        assert slugify("!!!") == "untitled"


class TestRenderMarkdown:

    def test_heading(self):
        """# 标题 -> <h1>"""
        assert "<h1>" in render_markdown("# Title")

    def test_bold(self):
        """**粗体** -> <strong>"""
        assert "<strong>" in render_markdown("**bold**")

    def test_link(self):
        """[text](url) -> <a href>"""
        html = render_markdown("[blog](https://example.com)")
        assert 'href="https://example.com"' in html

    def test_empty_string(self):
        """空字符串 -> 空"""
        assert render_markdown("") == ""


class TestGetArticleBySlug:

    async def test_found(self, db_session, article):
        """存在的 slug -> 返回文章"""
        result = await get_article_by_slug(db_session, "original")
        assert result is not None
        assert result.title == "Original"
        assert result.author is not None

    async def test_not_found(self, db_session):
        """不存在的 slug -> None"""
        assert await get_article_by_slug(db_session, "no-such") is None


class TestResolveSlugConflict:

    async def test_no_conflict(self, db_session):
        """slug 不存在 -> 原样返回"""
        assert await resolve_slug_conflict(db_session, "new-slug", 1) == "new-slug"

    async def test_conflict_appends_suffix(self, db_session, article):
        """slug 已存在 -> 追加后缀"""
        result = await resolve_slug_conflict(db_session, "original", 1)
        assert result.startswith("original-1-")


class TestSetArticleTags:

    async def test_set_tags(self, db_session, article, tag):
        """传入 tag_ids -> 文章标签被替换"""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        a = (await db_session.execute(
            select(Article).where(Article.id == article.id)
            .options(selectinload(Article.tags))
        )).scalar_one()
        await set_article_tags(db_session, a, [tag.id])
        assert len(a.tags) == 1
        assert a.tags[0].name == "python"

    async def test_empty_tags_skipped(self, db_session, article, tag):
        """空列表 -> 不操作"""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        a = (await db_session.execute(
            select(Article).where(Article.id == article.id)
            .options(selectinload(Article.tags))
        )).scalar_one()
        await set_article_tags(db_session, a, [])
        assert len(a.tags) == 1  # 保持原有关联


class TestQueryArticles:

    async def test_published_only(self, db_session, article):
        """默认只返回已发布文章"""
        items, total = await query_articles(db_session)
        assert total == 1
        assert items[0].slug == "original"

    async def test_with_pagination(self, db_session, article):
        """分页参数生效"""
        items, total = await query_articles(db_session, page=1, per_page=1)
        assert len(items) == 1
        assert total == 1

    async def test_filter_by_category(self, db_session, article, category):
        """按分类筛选"""
        items, total = await query_articles(db_session, category_id=category.id)
        assert total == 1

    async def test_search_by_title(self, db_session, article):
        """按关键词搜索标题"""
        items, total = await query_articles(db_session, search="Original")
        assert total == 1

    async def test_search_no_match(self, db_session, article):
        """搜不到 -> 空列表"""
        items, total = await query_articles(db_session, search="zzzzz")
        assert total == 0
        assert items == []

    async def test_author_sees_own_drafts(self, db_session, article, test_user):
        """is_published=None + author_id -> 作者的草稿也可见"""
        draft = Article(
            title="Draft", slug="draft",
            content="# d", content_html="<h1>d</h1>",
            summary="draft", is_published=False,
            author_id=test_user.id,
        )
        db_session.add(draft)
        await db_session.commit()
        items, total = await query_articles(
            db_session, is_published=None, author_id=test_user.id)
        assert total == 2

    async def test_admin_sees_published_and_own(self, db_session, article, test_user):
        """is_admin=True + author_id -> 已发布 + 自己的文章"""
        items, total = await query_articles(
            db_session, is_admin=True, author_id=test_user.id)
        assert total >= 1


class TestCreateArticle:

    async def test_basic_create(self, db_session, test_user):
        """基本创建 -> 返回文章含 slug/html"""
        result = await create_article(
            db_session,
            ArticleCreate(title="New Post", content="# Hello", summary="s"),
            author_id=test_user.id,
        )
        assert result.title == "New Post"
        assert result.slug == "new-post"
        assert "<h1>" in result.content_html
        assert result.author_id == test_user.id
        assert result.is_published is False

    async def test_create_with_category_and_tags(self, db_session, test_user, category, tag):
        """指定分类和标签 -> 关联正确"""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await create_article(
            db_session,
            ArticleCreate(title="Tagged", content="c", summary="s",
                          category_id=category.id, tags_id=[tag.id]),
            author_id=test_user.id,
        )
        assert result.category_id == category.id
        a = (await db_session.execute(
            select(Article).where(Article.id == result.id)
            .options(selectinload(Article.tags))
        )).scalar_one()
        assert len(a.tags) == 1

    async def test_slug_conflict_resolved(self, db_session, test_user, article):
        """标题重复 -> slug 自动加后缀"""
        result = await create_article(
            db_session,
            ArticleCreate(title="Original", content="# 2", summary="s"),
            author_id=test_user.id,
        )
        assert result.slug.startswith("original-")


class TestUpdateArticle:

    async def test_update_title_regenerates_slug(self, db_session, article):
        """修改标题 -> slug 重新生成"""
        updated = await update_article(
            db_session, article, ArticleUpdate(title="Updated Title"),
        )
        assert updated.title == "Updated Title"
        assert updated.slug == "updated-title"

    async def test_update_content_rerenders_html(self, db_session, article):
        """修改内容 -> content_html 同步更新"""
        updated = await update_article(
            db_session, article, ArticleUpdate(content="# New Heading"),
        )
        assert "<h1>New Heading</h1>" in updated.content_html

    async def test_publish_article(self, db_session, article):
        """发布文章 -> is_published=True"""
        updated = await update_article(
            db_session, article, ArticleUpdate(is_published=True),
        )
        assert updated.is_published is True
