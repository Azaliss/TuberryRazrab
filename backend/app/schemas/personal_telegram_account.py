from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PersonalTelegramAccountStatus


class PersonalTelegramAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    project_id: int
    display_name: str | None = None
    username: str | None = None
    phone: str | None = None
    telegram_user_id: str | None = None
    status: PersonalTelegramAccountStatus
    accepts_private: bool
    accepts_groups: bool
    accepts_channels: bool
    last_connected_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class PersonalTelegramAccountUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    accepts_private: bool | None = None
    accepts_groups: bool | None = None
    accepts_channels: bool | None = None


class PersonalTelegramAccountLoginRequest(BaseModel):
    project_id: int


class PersonalTelegramAccountLoginResponse(BaseModel):
    login_id: str
    qr_url: str
    expires_at: datetime | None = None


class PersonalTelegramAccountLoginStatusResponse(BaseModel):
    status: Literal["pending", "ready", "password_required", "completed", "error", "expired"]
    account: PersonalTelegramAccountResponse | None = None
    error: str | None = None


class PersonalTelegramAccountPasswordRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
