from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class ApplicationCommentMentionEntity(Base):
    """One validated @-mention of a user on an application comment.

    Written by BoardService.add_comment after checking the mentioned id
    against the comment's authorized-viewer set (job owner(s) + the
    application's current-stage assignee); never updated or deleted.
    Deliberately does not store a display name -- always resolved fresh
    from users_repository at read time, same as CommentDto.author_name.
    """

    __tablename__ = "application_comment_mention"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("application_comment.comment_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    mentioned_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="uq_application_comment_mention_comment_id",
        ),
    )
