from datetime import time
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampedModel
from app.models.enums import AutoReplyMode

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.bot import Bot
    from app.models.avito import AvitoAccount


class Client(TimestampedModel, table=True):
    __tablename__ = "clients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    status: str = Field(default="active")
    plan: str = Field(default="default")
    filter_keywords: Optional[str] = Field(default=None)
    require_reply_for_avito: bool = Field(default=False)
    hide_system_messages: bool = Field(default=True)
    auto_reply_enabled: bool = Field(default=False, nullable=False)
    auto_reply_mode: AutoReplyMode = Field(default=AutoReplyMode.always, sa_column_kwargs={"server_default": AutoReplyMode.always.value})
    auto_reply_always: bool = Field(default=False, nullable=False)
    auto_reply_start_time: Optional[time] = Field(default=None)
    auto_reply_end_time: Optional[time] = Field(default=None)
    auto_reply_timezone: Optional[str] = Field(default=None)
    auto_reply_text: Optional[str] = Field(default=None)

    users: List["User"] = Relationship(back_populates="client")
    bots: List["Bot"] = Relationship(back_populates="client")
    avito_accounts: List["AvitoAccount"] = Relationship(back_populates="client")


class ClientCreate(SQLModel):
    name: str
    plan: str = "default"
