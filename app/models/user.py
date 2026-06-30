from datetime import datetime, timezone
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.core.database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False, # 必需项,禁止为空
    )
    role: Mapped[str] = mapped_column(
        String(20),
        default=UserRole.USER.value,
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    password: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    ) # 密码存哈希值
    is_active: Mapped[bool] = mapped_column(
        Boolean, # 默认值
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(settings.tz),
        #使用 lambda 确保每次创建对象时都重新获取当前时间
        # （而不是模型定义时的固定时间）
    )

    articles = relationship("Article", back_populates="author")

