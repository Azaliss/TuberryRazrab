from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import BotStatus


class BotBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    bot_username: Optional[str]
    status: BotStatus
    group_chat_id: Optional[str]
    topic_mode: bool
    created_at: datetime


class BotCreateRequest(BaseModel):
    token: str
    bot_username: str | None = None
    group_chat_id: str | None = None
    topic_mode: bool = True


class BotUpdateRequest(BaseModel):
    bot_username: str | None = None
    group_chat_id: str | None = None
    topic_mode: bool | None = None
    status: BotStatus | None = None


class BotResponse(BotBase):
    pass
