from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DialogSource, DialogState


class DialogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    source: DialogSource
    avito_account_id: Optional[int]
    telegram_source_id: Optional[int]
    bot_id: int
    avito_dialog_id: str
    telegram_chat_id: Optional[str]
    telegram_topic_id: Optional[str]
    state: DialogState
    last_message_at: Optional[datetime]
    created_at: datetime
    external_reference: Optional[str] = None
    external_display_name: Optional[str] = None
    external_username: Optional[str] = None


class DialogMessagesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dialog: DialogResponse
    messages: list[dict]


class DialogMessageCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class DialogMessageSendResponse(BaseModel):
    status: str
    telegram_message_id: str
    telegram_chat_id: str
    telegram_topic_id: str | None = None
