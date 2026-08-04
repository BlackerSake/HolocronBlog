
import pytest
from sqlalchemy import select

from app.services.like_service import (
    update_like_count,
    change_like_status,
    change_like_status_cached,
    get_like_status,
    get_like_status_cached,
    batch_get_like_status,
    get_the_likers,
    get_user_history_likes,
)
from app.models.article import Article
from app.models.comment import Comment
from app.models.category import Category
from app.models.user import User
from app.models.like import Likes


@pytest.fixture
async def category(db_session):
    cat = Category(name="tech", description="tech")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest.fixture
async def published_article(db_session, test_user, category):
    article = Article(
        title="Published Article", slug="published-article",
        content="# Hello", content_html="<h1>Hello</h1>",
        summary="summary", is_published=True,
        author_id=test_user.id, category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest.fixture
async def existing_comment(db_session, published_article, test_user):
    comment = Comment(
        content="existing comment",
        article_id=published_article.id,
        author_id=test_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


class TestUpdateLikeCount:
    """update_like_count"""

    async def test_increment_article(self, db_session, published_article):
        """文章 like_count +1"""
        await update_like_count(db_session, published_article.id, "article", 1)
        await db_session.refresh(published_article)
        assert published_article.like_count == 1

    async def test_decrement_article(self, db_session, published_article):
        """文章 like_count -1"""
        await update_like_count(db_session, published_article.id, "article", 1)
        await update_like_count(db_session, published_article.id, "article", -1)
        await db_session.refresh(published_article)
        assert published_article.like_count == 0

    async def test_increment_comment(self, db_session, existing_comment):
        """评论 like_count +1"""
        await update_like_count(db_session, existing_comment.id, "comment", 1)
        await db_session.refresh(existing_comment)
        assert existing_comment.like_count == 1


class TestChangeLikeStatus:
    """change_like_status"""

    async def test_like_article(self, db_session, published_article, test_user):
        """点赞 -> 返回 True，like_count 增加"""
        is_liked = await change_like_status(db_session, test_user.id, published_article.id, "article")
        assert is_liked is True
        await db_session.refresh(published_article)
        assert published_article.like_count == 1

    async def test_unlike_article(self, db_session, published_article, test_user):
        """取消点赞 -> 返回 False，like_count 减少"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        is_liked = await change_like_status(db_session, test_user.id, published_article.id, "article")
        assert is_liked is False
        await db_session.refresh(published_article)
        assert published_article.like_count == 0

    async def test_multiple_users_like(self, db_session, published_article, test_user, other_user):
        """多个用户点赞 -> like_count 累加"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, other_user.id, published_article.id, "article")
        await db_session.refresh(published_article)
        assert published_article.like_count == 2

    async def test_like_comment(self, db_session, existing_comment, test_user):
        """点赞评论 -> 返回 True"""
        is_liked = await change_like_status(db_session, test_user.id, existing_comment.id, "comment")
        assert is_liked is True
        await db_session.refresh(existing_comment)
        assert existing_comment.like_count == 1

    async def test_like_record_saved(self, db_session, published_article, test_user):
        """点赞后数据库记录存在"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        record = await db_session.scalar(
            select(Likes).where(
                Likes.user_id == test_user.id,
                Likes.target_id == published_article.id,
                Likes.target_type == "article",
            )
        )
        assert record is not None

    async def test_unlike_record_removed(self, db_session, published_article, test_user):
        """取消点赞后数据库记录删除"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        record = await db_session.scalar(
            select(Likes).where(
                Likes.user_id == test_user.id,
                Likes.target_id == published_article.id,
                Likes.target_type == "article",
            )
        )
        assert record is None


class TestCachedLikeStatus:
    """Redis 点赞缓存"""

    async def test_toggle_updates_redis_and_stream(self, mock_redis, db_session, published_article, test_user):
        status = await change_like_status_cached(
            db_session, test_user.id, published_article.id, "article", True
        )

        assert status["is_liked"] is True
        assert status["like_count"] == 1
        assert status["changed"] is True
        assert str(test_user.id) in mock_redis.sets[f"like:article:{published_article.id}:users"]
        _, event = mock_redis.streams["like:events"][0]
        assert event["user_id"] == str(test_user.id)
        assert event["target_id"] == str(published_article.id)
        assert event["target_type"] == "article"
        assert event["is_liked"] == "1"
        assert await db_session.scalar(
            select(Likes.id).where(
                Likes.user_id == test_user.id,
                Likes.target_id == published_article.id,
                Likes.target_type == "article",
            )
        ) is None

    async def test_repeated_state_does_not_append_stream(self, mock_redis, db_session, published_article, test_user):
        """重复设置相同状态不会产生重复事件。"""
        await change_like_status_cached(
            db_session, test_user.id, published_article.id, "article", True
        )
        status = await change_like_status_cached(
            db_session, test_user.id, published_article.id, "article", True
        )

        assert status["is_liked"] is True
        assert status["like_count"] == 1
        assert status["changed"] is False
        assert len(mock_redis.streams["like:events"]) == 1

    async def test_status_reads_redis_first(self, mock_redis, db_session, published_article, test_user):
        base = f"like:article:{published_article.id}"
        mock_redis.strings[f"{base}:loaded"] = "1"
        mock_redis.sets[f"{base}:users"] = {
            str(test_user.id), "2", "3", "4", "5", "6", "7"
        }

        status = await get_like_status_cached(
            db_session, test_user.id, published_article.id, "article", 0
        )

        assert status["is_liked"] is True
        assert status["like_count"] == 7


class TestGetLikeStatus:
    """get_like_status"""

    async def test_not_liked(self, db_session, published_article, test_user):
        """未点赞 -> is_liked=False"""
        status = await get_like_status(
            db_session, test_user.id, published_article.id, "article", 0
        )
        assert status["is_liked"] is False
        assert status["like_count"] == 0
        assert status["target_id"] == published_article.id
        assert status["target_type"] == "article"

    async def test_liked(self, db_session, published_article, test_user):
        """已点赞 -> is_liked=True"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        status = await get_like_status(
            db_session, test_user.id, published_article.id, "article", 1
        )
        assert status["is_liked"] is True
        assert status["like_count"] == 1


class TestBatchGetLikeStatus:
    """batch_get_like_status"""

    async def test_empty_list(self, db_session, test_user):
        """空列表 -> 空字典"""
        assert await batch_get_like_status(db_session, test_user.id, [], "article") == {}

    async def test_batch_with_mixed_status(self, db_session, published_article, draft_article, test_user):
        """混合状态 -> 正确返回"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        status = await batch_get_like_status(
            db_session, test_user.id, [published_article.id, draft_article.id], "article"
        )
        assert status[published_article.id] is True
        assert status[draft_article.id] is False

    async def test_batch_all_liked(self, db_session, published_article, draft_article, test_user):
        """全部已赞 -> 全部 True"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, test_user.id, draft_article.id, "article")
        status = await batch_get_like_status(
            db_session, test_user.id, [published_article.id, draft_article.id], "article"
        )
        assert all(status.values())

    async def test_no_overlap_for_different_users(self, db_session, published_article, test_user, other_user):
        """用户A点赞不影响用户B的查询"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        status = await batch_get_like_status(
            db_session, other_user.id, [published_article.id], "article"
        )
        assert status[published_article.id] is False


class TestGetTheLikers:
    """get_the_likers"""

    async def test_no_likers(self, db_session, published_article):
        """无赞 -> 空列表"""
        likers = await get_the_likers(db_session, published_article.id, "article")
        assert likers == []

    async def test_returns_likers(self, db_session, published_article, test_user, other_user):
        """返回点赞者列表"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, other_user.id, published_article.id, "article")
        likers = await get_the_likers(db_session, published_article.id, "article")
        assert len(likers) == 2
        assert all(l.target_id == published_article.id for l in likers)

    async def test_limit(self, db_session, published_article, test_user, other_user):
        """limit 参数生效"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, other_user.id, published_article.id, "article")
        likers = await get_the_likers(db_session, published_article.id, "article", limit=1)
        assert len(likers) == 1


class TestGetUserHistoryLikes:
    """get_user_history_likes"""

    async def test_empty_history(self, db_session, test_user):
        """没有点赞 -> 空列表, total=0"""
        items, total = await get_user_history_likes(db_session, test_user.id, "article")
        assert items == []
        assert total == 0

    async def test_returns_article_likes(self, db_session, published_article, test_user):
        """点赞文章后 -> 返回记录"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        items, total = await get_user_history_likes(db_session, test_user.id, "article")
        assert total == 1
        assert items[0].target_id == published_article.id
        assert items[0].target_type == "article"

    async def test_filter_by_target_type(self, db_session, published_article, existing_comment, test_user):
        """按类型过滤 -> 只返回对应类型的记录"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, test_user.id, existing_comment.id, "comment")
        items, total = await get_user_history_likes(db_session, test_user.id, "article")
        assert total == 1
        assert items[0].target_type == "article"

    async def test_filter_by_user(self, db_session, published_article, test_user, other_user):
        """用户隔离 -> 只看自己的"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, other_user.id, published_article.id, "article")
        items, total = await get_user_history_likes(db_session, test_user.id, "article")
        assert total == 1

    async def test_pagination(self, db_session, published_article, draft_article, test_user):
        """分页参数生效"""
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        await change_like_status(db_session, test_user.id, draft_article.id, "article")
        items, total = await get_user_history_likes(db_session, test_user.id, "article", page=1, per_page=1)
        assert total == 2
        assert len(items) == 1

    async def test_ordered_by_time_desc(self, db_session, published_article, draft_article, test_user):
        """按时间倒序 -> 最新的在前"""
        await change_like_status(db_session, test_user.id, draft_article.id, "article")
        await change_like_status(db_session, test_user.id, published_article.id, "article")
        items, total = await get_user_history_likes(db_session, test_user.id, "article")
        assert total == 2
        assert items[0].target_id == published_article.id
        assert items[1].target_id == draft_article.id
