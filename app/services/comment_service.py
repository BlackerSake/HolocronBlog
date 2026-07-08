from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.comment import Comment
from app.schemas.comment import CommentOut
from app.services.notification_service import create_notification


async def create_comment(db: AsyncSession,
                   article_id: int,
                   author_id: int,
                   content: str,
                   parent_id: int | None) -> Comment:
        """创建评论

        完整流程：校验文章是否存在且已发布 -> 校验父评论合法性（跨文章检查）
        -> 构造评论对象 -> 根据是否为回复创建对应的通知。

        Args:
            db: 数据库会话
            article_id: 文章 ID
            author_id: 评论作者用户 ID
            content: 评论内容
            parent_id: 父评论 ID（回复评论时传入，根评论为 None）

        Returns:
            创建成功的评论对象

        Raises:
            HTTPException 404: 文章或父评论不存在
            HTTPException 400: 文章未发布、父评论已删除或跨文章回复
        """
        # 1. 检验文章是否已经存在
        article = await db.get(Article, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文章不存在"
            )
        if article.is_published == False:
              raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文章未发布"
            )
        
        # 2. 检验父评论是否存在
        parent_comment = None
        if parent_id:
            parent_comment = await db.get(Comment, parent_id)
            if parent_comment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="被回复的评论不存在"
                )
            # 父评论被删除时,是放行的.用户可能在删除前就点入了评论页面
            if parent_comment.article_id != article_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能跨文章回复评论"
                )
        # 3. 构造并返回新评论
        comment = Comment(
            content=content,
            author_id=author_id,
            article_id=article_id,
            parent_id=parent_id
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        if parent_comment:
            await create_notification(
                db,
                initiator_id=author_id,
                recipient_id=parent_comment.author_id,
                type="reply_to_comment",
                content="有人回复了你的评论",
                article_id=article_id,
                comment_id=comment.id,
                preview=content[:256],
            )
        else:
            await create_notification(
                db,
                initiator_id=author_id,
                recipient_id=article.author_id,
                type="comment_on_article",
                content="有人评论了你的文章",
                article_id=article_id,
                comment_id=comment.id,
                preview=content[:256],
            )

        return comment

def build_comment_tree(comments: list[Comment]) -> list[CommentOut]:
    """将扁平的评论列表组装成树形结构

    第一遍构建 id 到 CommentOut 的索引映射，所有节点 replies 初始化为空列表。
    第二遍根据 parent_id 将子节点挂载到父节点的 replies 中，
    parent_id 为 None 或父节点不在当前列表中的节点作为根节点返回。

    Args:
        comments: 扁平的评论列表（含作者关联加载）

    Returns:
        树形结构的根评论列表，每个节点下挂载其子评论的 replies 列表
    """
    comment_map: dict[int, CommentOut] = {}
    for comment in comments:
        node = CommentOut.model_validate(comment)
        node.replies = []
        comment_map[comment.id] = node

    roots: list[CommentOut] = []
    for comment in comments:
        node = comment_map[comment.id]
        if comment.parent_id and comment.parent_id in comment_map:
            comment_map[comment.parent_id].replies.append(node)
        else:
            roots.append(node)
    return roots
         

async def soft_delete_comment(
          db: AsyncSession,
          comment_id: int,
          user_id: int,
          user_role: str,
          ) -> Comment:
    """软删除评论

    校验评论存在性 -> 检查是否已删除 -> 权限校验（作者、文章作者或管理员可删除）
    -> 标记 is_deleted 为 True。

    Args:
        db: 数据库会话
        comment_id: 评论 ID
        user_id: 操作者用户 ID
        user_role: 操作者角色名

    Returns:
        软删除后的评论对象

    Raises:
        HTTPException 404: 评论不存在
        HTTPException 400: 评论已被删除
        HTTPException 403: 无删除权限
    """
    # 1. 获取评论
    comment = await db.get(Comment, comment_id)
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评论不存在"
        )
    if comment.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="评论已删除"
        )
    article_id = comment.article_id
    article = await db.get(Article, article_id)
    if user_id != comment.author_id and user_role != "admin" and article.author_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限删除该评论"
        )
    
    # 2. 删除评论
    comment.is_deleted = True
    # 3. 提交事务/返回结果
    await db.commit()
    await db.refresh(comment)
    return comment
    
async def get_article_comments(
          db: AsyncSession,
          article_id: int
          ) -> list[Comment]:
    """查询指定文章的全部评论，按创建时间升序排列

    一次性加载所有评论及其作者信息，不进行分页。
    通常配合 build_comment_tree 组装为树形结构后返回。

    Args:
        db: 数据库会话
        article_id: 文章 ID

    Returns:
        评论列表（含作者关联加载，按创建时间升序）
    """
    query = (
        select(Comment)
        .where(Comment.article_id == article_id,)
        .options(joinedload(Comment.author))
        .order_by(Comment.created_at)
    )
    result = await db.execute(query)
    comments = result.scalars().unique().all() # unique() 避免重复

    return comments



   
    
    


