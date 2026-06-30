
from datetime import datetime
from app.core.config import settings
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.permission import Permission
from app.core.database import Base

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", Integer, 
           ForeignKey("roles.id", ondelete="CASCADE"),
           primary_key=True),
    Column("permission_id", Integer,
           ForeignKey("permissions.id", ondelete="CASCADE"),
           primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    description: Mapped[str] = mapped_column(String(255))
    is_system: Mapped[bool] = mapped_column(default=False)
    create_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(settings.tz),
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary="role_permission",
        lazy="selectin",
    )


