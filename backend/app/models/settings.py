from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampedModel


class ProjectSettings(TimestampedModel, table=True):
    __tablename__ = "project_settings"

    id: Optional[int] = Field(default=1, primary_key=True)
    master_bot_token: Optional[str] = None
    master_bot_name: Optional[str] = None
