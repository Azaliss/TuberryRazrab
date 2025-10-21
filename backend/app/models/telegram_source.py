from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import TelegramSourceStatus

if TYPE_CHECKING:
    from app.models.bot import Bot
    from app.models.client import Client
    from app.models.dialog import Dialog


class TelegramSource(TimestampedModel, table=True):
    __tablename__ = "telegram_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    bot_id: int = Field(foreign_key="bots.id")
    token: str = Field(nullable=False)
    bot_username: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)
    status: TelegramSourceStatus = Field(default=TelegramSourceStatus.inactive)
    webhook_secret: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = Field(default=None, nullable=True)

    bot: "Bot" = Relationship()
    client: "Client" = Relationship(back_populates="telegram_sources")
    dialogs: List["Dialog"] = Relationship(back_populates="telegram_source")
