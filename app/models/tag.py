from sqlalchemy import String, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from datetime import datetime, timezone
class Tag(Base):
    __tablename__ = "tags" # 表名 tags 标签
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False # 禁止为空
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    articles = relationship("Article",
                            secondary="article_tags",
                            back_populates="tags")

