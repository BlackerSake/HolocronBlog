




import pytest
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime
from types import SimpleNamespace

from app.services.comment_service import (
    create_comment,
    get_article_comments,
    soft_delete_comment,
    build_comment_tree,
)
# tests/conftest.py

from app.models.user import User
from app.models.article import Article
from app.models.category import Category
from app.models.comment import Comment



@pytest.fixture
async def other_user(db_session):
    """测试用例: other_user"""
    from app.models.role import Role
    role = await db_session.execute(select(Role).where(Role.name == "user"))
    user = User(username="otheruser", password="password", email="other_user@example.com",
                role_id=role.scalar_one().id)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def category(db_session):
    """测试用例: category"""
    cat = Category(name="tech", description="tech category")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat

@pytest.fixture
async def published_article(db_session, test_user, category):
    """测试用例: 已发布的文章"""
    article = Article(
        title="Published Article",
        slug="published-article",
        content="# Hello",
        content_html="<h1>Hello</h1>",
        summary="summary",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article

@pytest.fixture
async def other_published_article(db_session, test_user, category):
    """测试用例: 另一篇已发布文章"""
    article = Article(
        title="Other Published Article",
        slug="other-published-article",
        content="# Other",
        content_html="<h1>Other</h1>",
        summary="other summary",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article

@pytest.fixture
async def draft_article(db_session, test_user, category):
    """测试用例: 草稿文章"""
    article = Article(
        title="Draft Article",
        slug="draft-article",
        content="# Draft",
        content_html="<h1>Draft</h1>",
        summary="draft summary",
        is_published=False,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article

@pytest.fixture
async def existing_comment(db_session, published_article, test_user):
    """测试用例: 已存在的评论"""
    comment = Comment(
        content="existing comment",
        article_id=published_article.id,
        author_id=test_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment
@pytest.fixture
async def deleted_comment(db_session, published_article, test_user):
    """测试用例: 已删除的评论"""
    comment = Comment(
        content="deleted comment",
        article_id=published_article.id,
        author_id=test_user.id,
        is_deleted=True,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment



class TestCreateComment:
    async def test_article_is_exiting(self, db_session,published_article, test_user):
        """文章存在 -> 正常创建"""
        comment = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="test",
            parent_id=None
        )
        assert comment is not None
        assert comment.id is not None
        assert comment.article_id == published_article.id
        assert comment.author_id == test_user.id
        assert comment.content == "test"
    async def test_article_is_not_exiting(self, db_session, test_user):
        """文章不存在 -> 404"""
        with pytest.raises(HTTPException) as exc:
            comment = await create_comment(
                db=db_session,
                article_id=999999,
                author_id=test_user.id,
                content="test",
                parent_id=None
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "文章不存在"
    
    async def test_article_is_published(self, db_session, draft_article, test_user):
        """文章未发布 -> 400"""
        with pytest.raises(HTTPException) as exc:
            comment = await create_comment(
                db=db_session,
                article_id=draft_article.id,
                author_id=test_user.id,
                content="test",
                parent_id=None
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == "文章未发布"
    
    async def test_parent_comment_is_not_existing(self, db_session, 
                                                  published_article, test_user):
        """父级评论不存在 -> 404"""
        with pytest.raises(HTTPException) as exc:
            comment = await create_comment(
                db=db_session,
                article_id=published_article.id,
                author_id=test_user.id,
                content="test",
                parent_id=9999999999
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "被回复的评论不存在"


    async def test_create_other_published_article_comment(
        self, db_session, published_article, other_published_article, test_user ):
        """跨文章评论 -> 400"""
        parent = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="parent comment",
            parent_id=None,)
        
        with pytest.raises(HTTPException) as exc:
            await create_comment(
                db=db_session,
                article_id=other_published_article.id,
                author_id=test_user.id,
                content="child comment",
                parent_id=parent.id
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == "不能跨文章回复评论"


    async def test_create_comment_success(
        self,
        db_session,
        published_article,
        test_user,
        existing_comment
    ):
        """创建成功,正常回复"""
        comment = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="test",
            parent_id=existing_comment.id
        )
        assert comment.content == "test"
        assert comment.author_id == test_user.id
        assert comment.article_id == published_article.id
        assert comment.parent_id == existing_comment.id


class TestSoftDeleteComment:
    async def test_delete_comment(self, db_session, existing_comment,test_user):
        comment = await soft_delete_comment(db_session, 
                                            existing_comment.id,
                                            user_id=test_user.id,
                                            user_role=test_user.role)
        assert comment.is_deleted == True

    async def test_delete_not_existing_comment(self, db_session, other_user, test_user):
        """删除不存在评论 -> 404"""
        with pytest.raises(HTTPException) as exc:
            await soft_delete_comment(
                db=db_session,
                comment_id=999,
                user_id=other_user.id,
                user_role=other_user.role,
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "评论不存在"
    
    async def test_delete_comment_id_deleted(self, db_session, deleted_comment, test_user):
        """删除已删除的评论 -> 404"""
        with pytest.raises(HTTPException) as exc:
            await soft_delete_comment(
                db=db_session,
                comment_id=deleted_comment.id,
                user_id=test_user.id,
                user_role=test_user.role
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == "评论已删除"

    async def test_delete_other_user_comment(self, db_session, test_user, other_user,published_article):
        """删除其他用户的评论 -> 403"""
        conmment1 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="test user's comment",
            parent_id=None
        )
        with pytest.raises(HTTPException) as exc:
            await soft_delete_comment(
                db=db_session,
                comment_id=conmment1.id,
                user_id=other_user.id,
                user_role=other_user.role
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == "无权限删除该评论"
    
    async def test_delete_comment_by_admin(
        self, db_session, test_user, admin_user, published_article
    ):
        """管理员删除评论 -> 删除成功"""
        comment1 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="test comment",
            parent_id=None,
        )
        await soft_delete_comment(
            db=db_session,
            comment_id=comment1.id,
            user_id=admin_user.id,
            user_role=admin_user.role,
        )
        assert comment1.is_deleted == True
    
    async def test_soft_delete_comment_by_author(
        self, db_session, other_user, test_user, published_article,
    ):
        """文章作者删除 评论 -> 删除成功"""
        comment1 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=other_user.id,
            content="test comment",
            parent_id=None,
        )
        await soft_delete_comment(
            db=db_session,
            comment_id=comment1.id,
            user_id=test_user.id,
            user_role=test_user.role
        )
        assert comment1.is_deleted == True
    

class TestGetAticleComments:

    async def test_get_article_with_no_comments(self, db_session, published_article):
        """测试获取无评论的文章 -> 返回空列表"""
        comments = await get_article_comments(db_session, published_article.id)
        assert comments == []
    
    async def test_get_article_with_comments(self, db_session, published_article, test_user, other_user):
        """测试获取有评论的文章 -> 返回评论列表"""
        comment1 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="comment1",
            parent_id=None
        )
        comment2 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=other_user.id,
            content="comment2",
            parent_id=comment1.id
        )
        comments = await get_article_comments(db=db_session, article_id=published_article.id)
        assert len(comments) == 2
        assert comments[0].id == comment1.id
        assert comments[1].id == comment2.id

    async def test_includes_deleted_comments(
        self, db_session, published_article, test_user,
    ):
        """已删除的评论也要返回"""
        comment1 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="alive",
            parent_id=None,
        )
        comment2 = await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="to delete",
            parent_id=None,
        )
        await soft_delete_comment(
            db=db_session,
            comment_id=comment2.id,
            user_id=test_user.id,
            user_role="user",
        )
        comments = await get_article_comments(
            db=db_session,
            article_id=published_article.id,
        )
        assert len(comments) == 2
        deleted = [c for c in comments if c.is_deleted]
        assert len(deleted) == 1

    async def test_does_not_return_other_article_comments(
        self, db_session, published_article, other_published_article, test_user,
    ):
        """不会混入其他文章的评论"""
        await create_comment(
            db=db_session,
            article_id=published_article.id,
            author_id=test_user.id,
            content="in first",
            parent_id=None,
        )
        await create_comment(
            db=db_session,
            article_id=other_published_article.id,
            author_id=test_user.id,
            content="in second",
            parent_id=None,
        )
        comments = await get_article_comments(
            db=db_session,
            article_id=published_article.id,
        )
        assert len(comments) == 1
        assert comments[0].content == "in first"




def make_comment(comment_id, content="test", parent_id=None, is_deleted=False, author_id=1):
    """构造一个ORM评论"""
    return SimpleNamespace(
        id=comment_id,
        content=content,
        parent_id=parent_id,
        is_deleted=is_deleted,
        author=SimpleNamespace(
            id=author_id,
            username=f"user{author_id}",
            role="user",
            email=f"user{author_id}@test.com",
            is_active=True,
            created_at=datetime(2025, 1, 1),
        ),
        created_at=datetime(2025, 1, 1),
    )


class TestBuildCommentTree:

    def test_empty_list(self):
        assert build_comment_tree([]) == []

    def test_single_top_level(self):
        c1 = make_comment(1)
        tree = build_comment_tree([c1])
        assert len(tree) == 1
        assert tree[0].id == 1
        assert tree[0].replies == []

    def test_multiple_top_level(self):
        c1 = make_comment(1)
        c2 = make_comment(2)
        c3 = make_comment(3)
        tree = build_comment_tree([c1, c2, c3])
        assert len(tree) == 3
        for node in tree:
            assert node.replies == []

    def test_two_level_nesting(self):
        c1 = make_comment(1)
        c2 = make_comment(2, parent_id=1)
        c3 = make_comment(3, parent_id=1)
        tree = build_comment_tree([c1, c2, c3])
        assert len(tree) == 1
        assert tree[0].id == 1
        assert len(tree[0].replies) == 2
        assert tree[0].replies[0].id == 2
        assert tree[0].replies[1].id == 3

    def test_three_level_nesting(self):
        c1 = make_comment(1)
        c2 = make_comment(2, parent_id=1)
        c3 = make_comment(3, parent_id=2)
        tree = build_comment_tree([c1, c2, c3])
        assert len(tree) == 1
        assert len(tree[0].replies) == 1
        assert len(tree[0].replies[0].replies) == 1
        assert tree[0].replies[0].replies[0].id == 3

    def test_deleted_parent_keeps_children(self):
        c1 = make_comment(1, is_deleted=True)
        c2 = make_comment(2, parent_id=1)
        tree = build_comment_tree([c1, c2])
        assert len(tree) == 1
        assert tree[0].content == "此评论已被删除"
        assert len(tree[0].replies) == 1
        assert tree[0].replies[0].id == 2

    def test_orphan_comment(self):
        """parent_id 指向不存在的评论，归为顶级"""
        c1 = make_comment(1, parent_id=999)
        tree = build_comment_tree([c1])
        assert len(tree) == 1
        assert tree[0].id == 1

    def test_complex_tree(self):
        """
        结构：
        c1 (顶级)
          c2 (回复 c1)
            c4 (回复 c2)
          c3 (回复 c1)
        c5 (顶级)
        """
        c1 = make_comment(1)
        c2 = make_comment(2, parent_id=1)
        c3 = make_comment(3, parent_id=1)
        c4 = make_comment(4, parent_id=2)
        c5 = make_comment(5)

        tree = build_comment_tree([c1, c2, c3, c4, c5])
        assert len(tree) == 2  # c1, c5
        assert len(tree[0].replies) == 2  # c2, c3
        assert len(tree[0].replies[0].replies) == 1  # c4
        assert tree[0].replies[0].replies[0].id == 4
        assert tree[0].replies[1].replies == []
        assert tree[1].id == 5







    




