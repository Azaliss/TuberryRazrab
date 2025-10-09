from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from app.models.base import TimestampedModel
from app.models.enums import MessageDirection, MessageStatus

if TYPE_CHECKING:
    from app.models.dialog import Dialog


class Message(TimestampedModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    dialog_id: int = Field(foreign_key="dialogs.id")
    direction: MessageDirection
    source_message_id: Optional[str] = Field(default=None, index=True)
    telegram_message_id: Optional[str] = Field(default=None, index=True)
    body: str
    attachments: Optional[str] = None
    status: MessageStatus = Field(default=MessageStatus.pending)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retries: int = Field(default=0)
    is_auto_reply: bool = Field(default=False, nullable=False)
    is_client_message: bool = Field(default=False, nullable=False)

    dialog: "Dialog" = Relationship(back_populates="messages")
