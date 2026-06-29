from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.comment import Comment
from app.schemas.comment import CommentOut


async def create_comment(db: AsyncSession, 
                   article_id: int, 
                   author_id: int, 
                   content: str, 
                   parent_id: int | None) -> Comment:
        """
        ## 创建评论
        1. 检验文章是否已经存在
        2. 查询父评论是否存在(软删除,放行)
        3. 构造并返回新评论
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

        return comment

def build_comment_tree(comments: list[Comment]) -> list[CommentOut]:
    """
    ## 将扁平的评论列表组装成树形结构

    - 第一遍：构建 id -> CommentOut 索引，所有节点的 replies 初始化为空列表
    - 第二遍：根据 parent_id 将子节点挂到父节点的 replies 中，  
      parent_id 为 None 或父节点不在当前列表中的节点作为根节点返回
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
    """
    ## 软删除评论
    1. 获取评论
    2. 删除评论
    3. 提交事务/返回结果
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
    """
    一次性查询某文章的所有评论
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



   
    
    


