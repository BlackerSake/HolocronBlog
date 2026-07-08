from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.article import Article
from app.models.comment import Comment
from app.models.user import User
from app.schemas.common import Response
from app.schemas.comment import CommentOut, CommentCreate
from app.services.comment_service import build_comment_tree, create_comment, get_article_comments, soft_delete_comment
from app.core.log import log_call
router  = APIRouter()

@log_call
@router.post(
    "/articles/{slug}/comments",
    response_model=Response[CommentOut],
    status_code=status.HTTP_201_CREATED)
async def create_comment_post(
    slug: str,
    comment_in: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建评论

    为指定文章创建新评论，支持回复已有评论（通过 parent_id 实现嵌套）。

    Args:
        slug: 文章 URL 标识
        comment_in: 评论创建数据（内容、父评论 ID 可选）
        user: 当前登录用户
        db: 数据库会话

    Returns:
        Response[CommentOut] — 创建的评论数据

    Raises:
        HTTPException 404: 文章不存在
    """
    article = await db.scalar(
        select(Article)
        .where(Article.slug == slug)
    )
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )
    comment = await create_comment(
        db=db,
        article_id=article.id,
        author_id=user.id,
        content=comment_in.content,
        parent_id=comment_in.parent_id
    )
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment.id)
        .options(joinedload(Comment.author))
    )
    return Response(data=result.scalar_one())

@log_call
@router.get(
    "/articles/{slug}/comments",
    response_model=Response[list[CommentOut]]
)
async def list_comments(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取文章所有评论

    查出指定文章的扁平评论列表，并组装为树形结构（含子评论嵌套）。

    Args:
        slug: 文章 URL 标识
        db: 数据库会话

    Returns:
        Response[list[CommentOut]] — 树形结构的评论列表

    Raises:
        HTTPException 404: 文章不存在
    """
    article = await db.scalar(
        select(Article)
        .where(Article.slug == slug)
    )
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )
    comments = await get_article_comments(db=db, article_id=article.id)
    tree = build_comment_tree(comments)    
    return Response(data=tree)
@log_call
@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除评论

    软删除指定评论，仅评论作者或管理员可操作。

    Args:
        comment_id: 评论 ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        None — 无内容返回（HTTP 204）
    """
 
    await soft_delete_comment(
        db=db,
        comment_id=comment_id,
        user_id=current_user.id,
        user_role=current_user.role
    )









