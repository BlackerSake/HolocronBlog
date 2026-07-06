from app.services.notification_service import (
    create_notification,
    get_unread_notifications_count,
)


class TestListNotification:

    async def test_get_notif_list_success(
        self, client, admin_headers, db_session, admin_user, test_user, other_user
    ):
        """获取用户通知列表 已读 + 未读 ->  200"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=admin_user.id,
            type="comment_on_article",
            content="有人评论了你的文章",
        )
        await create_notification(
            db_session,
            initiator_id=test_user.id,
            recipient_id=admin_user.id,
            type="reply_to_comment",
            content="有人回复了你",
        )
        await create_notification(
            db_session,
            initiator_id=admin_user.id,
            recipient_id=test_user.id,
            type="reply_to_comment",
            content="管理员自己的通知不应出现",
        )

        response = await client.get(
            "/notifications",
            params={"page": 1, "per_page": 10},
            headers=admin_headers,
        )
        data = response.json()["data"]

        assert response.status_code == 200
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert {item["content"] for item in data["items"]} == {
            "有人评论了你的文章",
            "有人回复了你",
        }


class TestGetUnreadNotificationCount:

    async def test_get_unread_notification_count_success(
        self, client, admin_headers, db_session, admin_user, other_user
    ):
        """获取用户未读通知数量 -> 200"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=admin_user.id,
            type="reply_to_comment",
            content="未读通知",
        )

        response = await client.get("/notifications/unread_count", headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1


class TestMarkAllNotificationRead:

    async def test_mark_all_notification_read_success(
        self, client, admin_headers, db_session, admin_user, test_user, other_user
    ):
        """标记所有通知为已读 -> 200"""
        await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=admin_user.id,
            type="reply_to_comment",
            content="未读通知 1",
        )
        await create_notification(
            db_session,
            initiator_id=test_user.id,
            recipient_id=admin_user.id,
            type="comment_on_article",
            content="未读通知 2",
        )

        response = await client.patch("/notifications/read-all", headers=admin_headers)

        assert response.status_code == 200
        assert await get_unread_notifications_count(db_session, admin_user.id) == 0


class TestMarkNotificationRead:

    async def test_mark_notification_read_success(
        self, client, admin_headers, db_session, admin_user, other_user
    ):
        """批量标记通知为已读 -> 200"""
        notification = await create_notification(
            db_session,
            initiator_id=other_user.id,
            recipient_id=admin_user.id,
            type="reply_to_comment",
            content="未读通知",
        )

        response = await client.patch(
            f"/notifications/{notification.id}/read",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert await get_unread_notifications_count(db_session, admin_user.id) == 0
