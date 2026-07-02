from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.core.database import Base
from app.models.role import Role

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False,
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    role_obj: Mapped["Role"] = relationship("Role", lazy="joined")
    email: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False,
    )
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(settings.tz),
    )

    articles = relationship("Article", back_populates="author")

    @property
    def role(self) -> str:
        """返回角色名称，兼容旧版字符串引用"""
        return self.role_obj.name if self.role_obj else "user"

