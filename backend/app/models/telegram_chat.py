from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedModel


class TelegramChat(TimestampedModel, table=True):
    __tablename__ = "telegram_chats"
    __table_args__ = (UniqueConstraint("bot_id", "chat_id", name="uq_bot_chat"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id", index=True)
    chat_id: str = Field(index=True)
    chat_type: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    is_forum: Optional[bool] = Field(default=None)
    is_active: bool = Field(default=True, nullable=False)
    last_status: Optional[str] = Field(default=None)
    joined_at: Optional[datetime] = Field(default=None)
    left_at: Optional[datetime] = Field(default=None)
