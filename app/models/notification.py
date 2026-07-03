
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.core.database import Base
from app.models.user import User

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String(255), nullable=False)

    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"), nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[str | None] = mapped_column(Text)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(settings.tz),
    )

    initiator: Mapped["User"] = relationship("User", foreign_keys=[initiator_id], lazy="joined")

