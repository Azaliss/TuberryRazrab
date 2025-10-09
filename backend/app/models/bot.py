from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import BotStatus

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.dialog import Dialog


class Bot(TimestampedModel, table=True):
    __tablename__ = "bots"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    token: str = Field(nullable=False)
    bot_username: Optional[str] = Field(default=None)
    status: BotStatus = Field(default=BotStatus.inactive)
    group_chat_id: Optional[str] = Field(default=None)
    topic_mode: bool = Field(default=True)
    webhook_secret: Optional[str] = Field(default=None, index=True)

    client: "Client" = Relationship(back_populates="bots")
    dialogs: List["Dialog"] = Relationship(back_populates="bot")
