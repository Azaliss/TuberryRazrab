from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict

from app.models.enums import AvitoAccountStatus


class AvitoAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    name: Optional[str]
    api_client_id: Optional[str]
    status: AvitoAccountStatus
    token_expires_at: Optional[datetime]
    bot_id: Optional[int]
    project_id: Optional[int]
    created_at: datetime
    monitoring_enabled: bool
    webhook_enabled: bool
    webhook_url: Optional[str]
    webhook_last_error: Optional[str]


class AvitoAccountCreateRequest(BaseModel):
    api_client_id: str
    api_client_secret: str
    name: str | None = None
    access_token: str | None = None
    token_expires_at: datetime | None = None
    bot_id: int | None = None
    monitoring_enabled: bool | None = True
    project_id: int | None = None


class AvitoAccountUpdateRequest(BaseModel):
    name: str | None = None
    status: AvitoAccountStatus | None = None
    api_client_id: str | None = None
    api_client_secret: str | None = None
    access_token: str | None = None
    token_expires_at: datetime | None = None
    bot_id: int | None = None
    monitoring_enabled: bool | None = None
    project_id: int | None = None
