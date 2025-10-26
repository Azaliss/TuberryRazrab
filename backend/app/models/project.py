from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import AutoReplyMode

if TYPE_CHECKING:
    from app.models.personal_telegram_account import PersonalTelegramAccount

class Project(TimestampedModel, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    name: str = Field(index=True)
    slug: Optional[str] = Field(
        default=None,
        index=True,
        sa_column_kwargs={"unique": True},
    )
    description: Optional[str] = Field(default=None)
    status: str = Field(default="active")
    bot_id: Optional[int] = Field(
        default=None,
        foreign_key="bots.id",
        sa_column_kwargs={"unique": True},
    )
    filter_keywords: Optional[str] = Field(default=None)
    require_reply_for_sources: bool = Field(default=False)
    hide_system_messages: bool = Field(default=True)
    auto_reply_enabled: bool = Field(default=False, nullable=False)
    auto_reply_mode: AutoReplyMode = Field(
        default=AutoReplyMode.always,
        sa_column_kwargs={"server_default": AutoReplyMode.always.value},
    )
    auto_reply_always: bool = Field(default=False, nullable=False)
    auto_reply_start_time: Optional[time] = Field(default=None)
    auto_reply_end_time: Optional[time] = Field(default=None)
    auto_reply_timezone: Optional[str] = Field(default=None)
    auto_reply_text: Optional[str] = Field(default=None)
    topic_intro_template: Optional[str] = Field(default=None)
