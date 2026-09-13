import json

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.websocket import wbmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.like import LikeHistoryOut, LikeMutationOut, LikeStateIn, LikeStatusOut
from app.services.like_service import (
    change_like_status_cached,
    enrich_like_history_items,
    get_article_like_target,
    get_comment_like_target,
    get_like_status_cached,
    get_user_history_likes,
)
from app.core.notification_stream import append_notification_event


router = APIRouter()


@router.put("/articles/{slug}/like", response_model=LikeMutationOut)
async def set_article_like_state(
    slug: str,
    payload: LikeStateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    设置当前用户对文章的点赞状态。

    接口接收期望的最终状态，重复提交相同状态不会产生重复点赞记录或
    Redis Stream 事件。

    Args:
        slug: 文章 URL 标识
        payload: 期望的最终点赞状态
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        LikeMutationOut: 最终点赞状态、点赞总数和本次是否实际变更

    Raises:
        HTTPException 404: 文章不存在、未发布或已删除
    """
    target = await get_article_like_target(db, slug)
    if target is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    article_id, author_id, _ = target

    status = await change_like_status_cached(
        db,
        current_user.id,
        article_id,
        "article",
        payload.is_liked,
    )

    if status["is_liked"] and status["changed"]:
        await append_notification_event(
            initiator_id=current_user.id,
            recipient_id=author_id,
            type="like_article",
            content="有人赞了你的文章",
            article_id=article_id,
        )
    if status["changed"]:
        # 发送 WebSocket 消息通知前端点赞状态变更
        await wbmanager.send_personal_message(current_user.id, json.dumps({
            "type": "like_changed",
            "user_id": current_user.id,
            **status,
        }))
    return LikeMutationOut(**status)


@router.put("/comments/{comment_id}/like", response_model=LikeMutationOut)
async def set_comment_like_state(
    comment_id: int,
    payload: LikeStateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    设置当前用户对评论的点赞状态。

    接口接收期望的最终状态，重复提交相同状态不会产生重复点赞记录或
    Redis Stream 事件。

    Args:
        comment_id: 评论 ID
        payload: 期望的最终点赞状态
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        LikeMutationOut: 最终点赞状态、点赞总数和本次是否实际变更

    Raises:
        HTTPException 404: 评论不存在
    """
    target = await get_comment_like_target(db, comment_id)
    if target is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    target_id, author_id, article_id, _ = target
    status = await change_like_status_cached(
        db,
        current_user.id,
        target_id,
        "comment",
        payload.is_liked,
    )
    if status["is_liked"] and status["changed"]:
        await append_notification_event(
            initiator_id=current_user.id,
            recipient_id=author_id,
            type="like_comment",
            content="有人赞了你的评论",
            article_id=article_id,
            comment_id=target_id,
        )
    if status["changed"]:
        await wbmanager.send_personal_message(current_user.id, json.dumps({
            "type": "like_changed",
            "user_id": current_user.id,
            **status,
        }))
    return LikeMutationOut(**status)

@router.get("/articles/{slug}/like-status", response_model=LikeStatusOut)
async def article_like_status(slug: str,
                              current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    """
    查询当前用户对文章的点赞状态

    Args:
        slug: 文章 URL 标识
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        LikeStatusOut — 包含点赞状态及点赞总数
    """
    target = await get_article_like_target(db, slug)
    if target is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    article_id, _, like_count = target

    status = await get_like_status_cached(
        db, current_user.id, article_id, "article", like_count
    )
    return LikeStatusOut(**status)

@router.get("/comments/{comment_id}/like-status", response_model=LikeStatusOut)
async def comment_like_status(comment_id: int,
                              current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    """
    获取当前用户对评论的点赞状态

    Args:
        comment_id: 评论 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        LikeStatusOut — 包含点赞状态及点赞总数
    """
    target = await get_comment_like_target(db, comment_id)
    if target is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    target_id, _, _, like_count = target
    status = await get_like_status_cached(
        db, current_user.id, target_id, "comment", like_count
    )
    return LikeStatusOut(**status)
@router.get("/me/like-history", response_model=list[LikeHistoryOut])
async def get_liked_hisotry(target_type: str | None = None,
                            current_user: User = Depends(get_current_user),
                            page: int = Query(1, ge=1),
                            per_page: int = Query(20, le=50),
                            db: AsyncSession = Depends(get_db)):
    """
    获取当前用户的点赞历史

    支持按目标类型（article/comment）筛选，支持分页。

    Args:
        target_type: 目标类型筛选（"article" 或 "comment"，可选）
        current_user: 当前登录用户
        page: 页码，从 1 开始
        per_page: 每页数量，默认 20，最大 50
        db: 数据库会话

    Returns:
        list[LikeHistoryOut] — 点赞历史列表
    """
    if target_type and target_type not in ("article", "comment"):
        return []
    items, total = await get_user_history_likes(db, current_user.id, target_type, page, per_page)
    return await enrich_like_history_items(db, items)

@router.get("/users/{user_id}/like-history", response_model=list[LikeHistoryOut])
async def get_users_liked_history_router(user_id: int,
                                         target_type: str | None = None,
                                         page: int = Query(1, ge=1),
                                         per_page: int = Query(20, le=50),
                                         db: AsyncSession = Depends(get_db)):
    """
    获取指定用户的点赞历史

    支持按目标类型（article/comment）筛选，支持分页。

    Args:
        user_id: 目标用户 ID
        target_type: 目标类型筛选（"article" 或 "comment"，可选）
        page: 页码，从 1 开始
        per_page: 每页数量，默认 20，最大 50
        db: 数据库会话

    Returns:
        list[LikeHistoryOut] — 点赞历史列表
    """
    if target_type and target_type not in ("article", "comment"):
        return []
    items, total = await get_user_history_likes(db, user_id, target_type, page, per_page)
    return await enrich_like_history_items(db, items)
