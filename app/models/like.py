



from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base
from app.models.user import User


class Likes(Base):
    """定义点赞表"""
    __tablename__ = "likes"
    
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id",
            name="unique_like_per_user_per_target"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 目标类型: article & comment
    # 不做外键约束, target_id 指向哪张表取决于 target_type
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    create_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(settings.tz)
    )

    user: Mapped["User"] = relationship("User", lazy="joined")