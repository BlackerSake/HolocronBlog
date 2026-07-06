



from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Likes(Base):
    """定义点赞表"""
    __tablename__ = "likes"
    
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)

    target_type: Mapped[str] = mapped_column(primary_key=True)
    like_count: Mapped[int] = mapped_column(default=0)
    
