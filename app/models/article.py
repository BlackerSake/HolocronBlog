from datetime import datetime, timezone
from sqlalchemy import (
    Column, ForeignKey, Integer, String, 
    Text, Boolean, DateTime, Table
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.core.database import Base

"""创建文章表"""

# 文章与标签的多对多关系表
article_tags = Table(
    "article_tags", # 表名
    Base.metadata, # 元数据
    Column("article_id",Integer, 
           ForeignKey("articles.id",ondelete="CASCADE"),
           primary_key=True ),
    Column("tag_id",Integer,
           ForeignKey("tags.id",ondelete="CASCADE"),
           primary_key=True )
           )

class Article(Base):
    """定义文章 模型"""
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    # "铅条", 在 Web 开发中表示将标题转成可用于网址的字符串.
    # 是URL 友好的唯一标识符
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False) 
    #用以储存服务端渲染的html,避免每次请求重新渲染
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image: Mapped[str] = mapped_column(String(255), nullable=True) # 封面图片

    # 状态
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False) # 软删除

    # 时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(settings.tz),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(settings.tz),
        onupdate=lambda: datetime.now(settings.tz),
    )
    # 浏览量字段
    views: Mapped[int] = mapped_column(Integer, server_default="0")

    # 关联
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))

    # 一对多关系a,c  与多对多关系: tags
    author = relationship("User", back_populates="articles")
    category = relationship("Category", back_populates="articles")
    tags = relationship("Tag", secondary=article_tags, back_populates="articles")