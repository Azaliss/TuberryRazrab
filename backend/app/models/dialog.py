from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, String
from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import DialogSource, DialogState

if TYPE_CHECKING:
    from app.models.bot import Bot
    from app.models.avito import AvitoAccount
    from app.models.message import Message
    from app.models.telegram_source import TelegramSource


class Dialog(TimestampedModel, table=True):
    __tablename__ = "dialogs"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    source: str = Field(
        default=DialogSource.avito.value,
        sa_column=Column(String(32), default=DialogSource.avito.value, nullable=False),
    )
    avito_account_id: Optional[int] = Field(default=None, foreign_key="avito_accounts.id")
    telegram_source_id: Optional[int] = Field(default=None, foreign_key="telegram_sources.id")
    bot_id: int = Field(foreign_key="bots.id")
    avito_dialog_id: str = Field(index=True)
    telegram_topic_id: Optional[str] = Field(default=None, index=True)
    telegram_chat_id: Optional[str] = Field(default=None)
    state: DialogState = Field(default=DialogState.active)
    last_message_at: Optional[datetime] = None
    topic_intro_sent: bool = Field(default=False, nullable=False)
    auto_reply_last_sent_at: Optional[datetime] = Field(default=None, nullable=True)
    auto_reply_scheduled_at: Optional[datetime] = Field(default=None, nullable=True)
    external_reference: Optional[str] = Field(default=None, index=True)
    external_display_name: Optional[str] = Field(default=None)
    external_username: Optional[str] = Field(default=None)

    bot: "Bot" = Relationship(back_populates="dialogs")
    avito_account: Optional["AvitoAccount"] = Relationship(back_populates="dialogs")
    telegram_source: Optional["TelegramSource"] = Relationship(back_populates="dialogs")
    messages: List["Message"] = Relationship(back_populates="dialog")
