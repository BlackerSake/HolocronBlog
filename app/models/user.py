from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from app.core.database import Base
from app.models.role import Role

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False,
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    role_obj: Mapped["Role"] = relationship("Role", lazy="joined")
    email: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False,
    )
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 个人资料
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    articles = relationship("Article", back_populates="author")

    @property
    def role(self) -> str:
        """返回角色名称，兼容旧版字符串引用"""
        return self.role_obj.name if self.role_obj else "user"
