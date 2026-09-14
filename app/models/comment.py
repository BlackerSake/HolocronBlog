

from datetime import datetime, timezone
from sqlalchemy import Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.user import User

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="SET NULL"), nullable=True)
    # 建表时 `parent_id` 外键的 `ondelete` 策略设为 `SET NULL`
    # 父评论被删时子评论不会跟着丢失，`parent_id` 变为 `NULL`,子评论变成顶级评论
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 发布后不可编辑
    
    author: Mapped["User"] = relationship()

    like_count: Mapped[int] = mapped_column(default=0)
