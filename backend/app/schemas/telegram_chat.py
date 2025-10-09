from typing import Optional

from pydantic import BaseModel, ConfigDict


class TelegramChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chat_id: str
    title: Optional[str] = None
    chat_type: Optional[str] = None
    username: Optional[str] = None
    is_forum: Optional[bool] = None
    is_active: bool
    last_status: Optional[str] = None
