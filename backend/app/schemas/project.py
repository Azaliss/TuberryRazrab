from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AutoReplyMode


class ProjectBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    name: str
    slug: Optional[str]
    description: Optional[str]
    status: str
    bot_id: Optional[int]
    filter_keywords: Optional[str]
    require_reply_for_sources: bool
    hide_system_messages: bool
    auto_reply_enabled: bool
    auto_reply_mode: AutoReplyMode
    auto_reply_always: bool
    auto_reply_start_time: Optional[time]
    auto_reply_end_time: Optional[time]
    auto_reply_timezone: Optional[str]
    auto_reply_text: Optional[str]
    topic_intro_template: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class ProjectResponse(ProjectBase):
    pass


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9\-_.]+$")
    description: str | None = Field(default=None, max_length=500)
    bot_id: int | None = None
    bot_token: str | None = Field(default=None, max_length=128)
    bot_group_chat_id: str | None = Field(default=None, max_length=64)
    bot_topic_mode: bool | None = None
    use_bot_as_source: bool | None = None
    status: str | None = None
    filter_keywords: str | None = None
    require_reply_for_sources: bool | None = None
    hide_system_messages: bool | None = None
    auto_reply_enabled: bool | None = None
    auto_reply_mode: AutoReplyMode | None = None
    auto_reply_always: bool | None = None
    auto_reply_start_time: time | None = None
    auto_reply_end_time: time | None = None
    auto_reply_timezone: str | None = None
    auto_reply_text: str | None = Field(default=None, max_length=2000)
    topic_intro_template: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_bot_fields(self) -> "ProjectCreateRequest":
        bot_id = getattr(self, "bot_id", None)
        bot_token = (getattr(self, "bot_token", None) or "").strip()
        if not bot_id and not bot_token:
            raise ValueError("Укажите Telegram-бота или его токен")
        if bot_id and bot_token:
            raise ValueError("Нельзя одновременно указать существующий бот и токен нового бота")
        if bot_token:
            self.bot_token = bot_token
        if self.bot_group_chat_id:
            self.bot_group_chat_id = self.bot_group_chat_id.strip()
        return self


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9\-_.]+$")
    description: str | None = Field(default=None, max_length=500)
    bot_id: int | None = Field(default=None)
    bot_token: str | None = Field(default=None, max_length=128)
    bot_group_chat_id: str | None = Field(default=None, max_length=64)
    bot_topic_mode: bool | None = None
    use_bot_as_source: bool | None = None
    status: str | None = None
    filter_keywords: str | None = None
    require_reply_for_sources: bool | None = None
    hide_system_messages: bool | None = None
    auto_reply_enabled: bool | None = None
    auto_reply_mode: AutoReplyMode | None = None
    auto_reply_always: bool | None = None
    auto_reply_start_time: time | None = None
    auto_reply_end_time: time | None = None
    auto_reply_timezone: str | None = None
    auto_reply_text: str | None = Field(default=None, max_length=2000)
    topic_intro_template: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_bot_fields(self) -> "ProjectUpdateRequest":
        bot_id = getattr(self, "bot_id", None)
        bot_token = (getattr(self, "bot_token", None) or "").strip()
        if bot_id and bot_token:
            raise ValueError("Нельзя одновременно указать существующий бот и токен нового бота")
        if bot_token:
            self.bot_token = bot_token
        if self.bot_group_chat_id:
            self.bot_group_chat_id = self.bot_group_chat_id.strip()
        return self
