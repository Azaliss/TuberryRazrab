from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import AvitoAccountStatus

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.dialog import Dialog


class AvitoAccount(TimestampedModel, table=True):
    __tablename__ = "avito_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id")
    name: Optional[str] = None
    api_client_id: Optional[str] = None
    api_client_secret: Optional[str] = None
    access_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    status: AvitoAccountStatus = Field(default=AvitoAccountStatus.active)
    bot_id: Optional[int] = Field(default=None, foreign_key="bots.id")
    monitoring_enabled: bool = Field(default=True)
    webhook_secret: Optional[str] = Field(default=None, index=True)
    webhook_url: Optional[str] = Field(default=None)
    webhook_enabled: bool = Field(default=False, nullable=False)
    webhook_last_error: Optional[str] = Field(default=None)

    client: "Client" = Relationship(back_populates="avito_accounts")
    dialogs: list["Dialog"] = Relationship(back_populates="avito_account")
