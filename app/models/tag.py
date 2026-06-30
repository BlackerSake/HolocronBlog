from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.core.database import Base
from datetime import datetime
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
        default=lambda: datetime.now(settings.tz),
    )
    articles = relationship("Article",
                            secondary="article_tags",
                            back_populates="tags")


