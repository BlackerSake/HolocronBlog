import json
from unittest.mock import AsyncMock

from app.core.websocket import wbmanager
from app.models.notification import Notification
from app.services.notification_service import (
    create_notification,
    get_notifications_list,
    get_unread_notifications_count,
    mark_all_notification_is_read,
    mark_notification_is_read,
)


class TestCreateNotification:

    async def test_pushes_created_notification_in_real_time(
        self, db_session, test_user, other_user, monkeypatch
    ):
        send = AsyncMock()
        monkeypatch.setattr(wbmanager, "send_personal_message", send)

        notification = await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="like_article",
            content="有人赞了你的文章",
        )

        recipient_id, message = send.await_args.args
        assert recipient_id == test_user.id
        assert json.loads(message) == {
            "type": "notification_created",
            "notification_id": notification.id,
        }

    async def test_someone_reply_to_me(
        self, db_session, test_user, other_user, existing_comment
    ):
        """测试有人回复我 -> 我收到对应消息"""
        notification = await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="someone_reply_to_me",
            content="有人回复了你",
            comment_id=existing_comment.id,
        )

        assert notification.initiator_id == other_user.id
        assert notification.recipient_id == test_user.id
        assert notification.comment_id == existing_comment.id
        assert notification.is_read is False

    async def test_someone_comment_on_my_article(
        self, db_session, test_user, other_user, article
    ):
        """测试有人评论我的文章 -> 我收到对应消息"""
        notification = await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="someone_comment_on_my_article",
            content="有人评论了你的文章",
            article_id=article.id,
            preview="评论摘要",
        )

        assert notification.initiator_id == other_user.id
        assert notification.recipient_id == test_user.id
        assert notification.article_id == article.id
        assert notification.preview == "评论摘要"

    async def test_reply_to_myself(self, db_session, test_user, existing_comment):
        """测试自己回复自己 -> 不产生通知"""
        notification = await create_notification(
            db_session,
            initiator_id=test_user.id,
            recipient_id=test_user.id,
            type="someone_reply_to_me",
            content="自己回复自己",
            comment_id=existing_comment.id,
        )

        assert notification is None


class TestGetNotificationList:

    async def test_get_notification_list(self, db_session, test_user, other_user, article):
        """测试获取通知列表"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="reply_to_comment",
            content="第一条",
            article_id=article.id,
        )
        await create_notification(
            db_session,
            initiator_id=test_user.id,
            recipient_id=other_user.id,
            type="reply_to_comment",
            content="别人的通知",
        )

        items, total = await get_notifications_list(db_session, user_id=test_user.id)

        assert total == 1
        assert len(items) == 1
        assert items[0].content == "第一条"
        assert items[0].article_slug == article.slug

    async def test_with_pagination(self, db_session, test_user, other_user):
        """测试分页"""
        for index in range(3):
            await create_notification(
                db_session,
                initiator_id=other_user.id,
                recipient_id=test_user.id,
                type="reply_to_comment",
                content=f"第 {index} 条",
            )

        items, total = await get_notifications_list(
            db_session, page=2, per_page=2, user_id=test_user.id
        )

        assert total == 3
        assert len(items) == 1


class TestGetUnreadNotificationCount:

    async def test_get_unread_notification_count_not_0(
        self, db_session, test_user, other_user
    ):
        """测试获取未读通知数量 -> 返回 count"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="reply_to_comment",
            content="未读通知",
        )

        assert await get_unread_notifications_count(db_session, test_user.id) == 1

    async def test_get_unread_notification_count_0(self, db_session, test_user):
        """测试获取未读通知数量 -> 0"""
        assert await get_unread_notifications_count(db_session, test_user.id) == 0


class TestMarkNotificationIsRead:

    async def test_mark_notification_is_read_success(
        self, db_session, test_user, other_user
    ):
        """测试标记通知为已读 -> 成功"""
        notification = await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="reply_to_comment",
            content="未读通知",
        )

        ok = await mark_notification_is_read(db_session, notification.id, test_user.id)
        saved = await db_session.get(Notification, notification.id)

        assert ok is True
        assert saved.is_read is True

    async def test_mark_None_notification_is_read(self, db_session, test_user):
        """测试标记通知为已读 -> 无此通"""
        assert await mark_notification_is_read(db_session, 999999, test_user.id) is False


class TestMarkAllNotificationIsRead:

    async def test_mark_all_notification_is_read_success(
        self, db_session, test_user, other_user
    ):
        """测试批量标记所有通知为已读 -> 批量成功"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="reply_to_comment",
            content="未读通知 1",
        )
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=test_user.id,
            type="comment_on_article",
            content="未读通知 2",
        )

        count = await mark_all_notification_is_read(db_session, test_user.id)

        assert count == 2
        assert await get_unread_notifications_count(db_session, test_user.id) == 0

    async def test_mark_all_notification_is_read_0(self, db_session, test_user):
        """测试批量标记所有通知为已读 -> 0"""
        assert await mark_all_notification_is_read(db_session, test_user.id) == 0
