from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampedModel


class WebhookEvent(TimestampedModel, table=True):
    __tablename__ = "webhook_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    payload: str
    status: str = Field(default="pending")
    error: Optional[str] = None
