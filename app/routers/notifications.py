from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.log import log_call
from app.models.user import User
from app.schemas.common import Paginated, Response
from app.schemas.notifications import NotificationListItem, UnreadNotificationCount
from app.services.notification_service import (
    get_notifications_list,
    get_unread_notifications_count,
    mark_all_notification_is_read,
    mark_notification_is_read,
)

router = APIRouter(prefix="/notifications")


@log_call
@router.get("", response_model=Response[Paginated[NotificationListItem]])
async def get_notif_list(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取用户通知列表 已读 + 未读"""
    items, total = await get_notifications_list(
        db, page=page, per_page=per_page, user_id=current_user.id
    )
    return Response(data={
        "items": items, "total": total,
        "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@log_call
@router.get("/unread_count", response_model=Response[UnreadNotificationCount])
async def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户未读通知数量"""
    count = await get_unread_notifications_count(db, user_id=current_user.id)
    return Response(data=UnreadNotificationCount(count=count))


@log_call
@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    ok = await mark_notification_is_read(db, notification_id=notification_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return Response(message="已读")


@log_call
@router.patch("/read-all")
async def mark_all_notification_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量标记所有通知为已读"""
    await mark_all_notification_is_read(db, user_id=current_user.id)
    return Response(message="标记成功")
