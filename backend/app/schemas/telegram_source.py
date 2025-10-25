from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import TelegramSourceStatus


class TelegramSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    bot_id: int
    project_id: Optional[int]
    display_name: Optional[str]
    bot_username: Optional[str]
    status: TelegramSourceStatus
    webhook_secret: Optional[str]
    description: Optional[str]
    webhook_url: Optional[str] = None


class TelegramSourceCreateRequest(BaseModel):
    token: str
    bot_id: int
    project_id: int
    display_name: Optional[str] = None
    description: Optional[str] = None


class TelegramSourceUpdateRequest(BaseModel):
    bot_id: Optional[int] = None
    project_id: Optional[int] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TelegramSourceStatus] = None
