from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    plan: str
    created_at: datetime
    filter_keywords: Optional[str] = None
    require_reply_for_avito: bool
    hide_system_messages: bool
    auto_reply_enabled: bool
    auto_reply_always: bool
    auto_reply_start_time: Optional[time] = None
    auto_reply_end_time: Optional[time] = None
    auto_reply_timezone: Optional[str] = None
    auto_reply_text: Optional[str] = None


class ClientCreateRequest(BaseModel):
    name: str
    plan: str | None = "default"
    filter_keywords: str | None = None
    require_reply_for_avito: bool | None = False
    hide_system_messages: bool | None = True
    auto_reply_enabled: bool | None = False
    auto_reply_always: bool | None = False
    auto_reply_start_time: time | None = None
    auto_reply_end_time: time | None = None
    auto_reply_timezone: str | None = None
    auto_reply_text: str | None = Field(default=None, max_length=2000)


class ClientResponse(ClientBase):
    pass


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    filter_keywords: Optional[str] = None
    require_reply_for_avito: Optional[bool] = None
    hide_system_messages: Optional[bool] = None
    auto_reply_enabled: Optional[bool] = None
    auto_reply_always: Optional[bool] = None
    auto_reply_start_time: Optional[time] = None
    auto_reply_end_time: Optional[time] = None
    auto_reply_timezone: Optional[str] = None
    auto_reply_text: Optional[str] = Field(default=None, max_length=2000)
