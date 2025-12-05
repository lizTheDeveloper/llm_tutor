"""
InteractionLog model for tracking user interactions.
Stores all user interactions with embeddings for semantic similarity search.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from src.models.base import Base


class InteractionLog(Base):
    """
    InteractionLog model for storing all user interactions.
    Tracks exercises, chat messages, hints, and other user activities.
    """

    __tablename__ = "interaction_logs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Interaction details
    interaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )  # 'exercise_completion', 'chat_message', 'hint_request', 'code_submission', etc.

    context_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # 'exercise', 'chat', 'code_review', 'onboarding', etc.

    context_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )  # ID of related entity (exercise_id, conversation_id, etc.)

    interaction_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )  # Flexible storage for interaction-specific data

    # Vector embedding for semantic search
    interaction_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),
        nullable=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    def __repr__(self) -> str:
        """String representation of InteractionLog."""
        return f"<InteractionLog(id={self.id}, user_id={self.user_id}, type='{self.interaction_type}')>"
