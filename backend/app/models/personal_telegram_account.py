from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampedModel
from app.models.enums import PersonalTelegramAccountStatus

class PersonalTelegramAccount(TimestampedModel, table=True):
    __tablename__ = "personal_telegram_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    project_id: int = Field(foreign_key="projects.id")
    display_name: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = Field(default=None, index=True)
    telegram_user_id: Optional[str] = Field(default=None, index=True)
    status: PersonalTelegramAccountStatus = Field(
        default=PersonalTelegramAccountStatus.pending,
        sa_column_kwargs={"nullable": False},
    )
    session_payload: Optional[str] = Field(default=None)
    accepts_private: bool = Field(default=False, nullable=False)
    accepts_groups: bool = Field(default=False, nullable=False)
    accepts_channels: bool = Field(default=False, nullable=False)
    last_connected_at: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
