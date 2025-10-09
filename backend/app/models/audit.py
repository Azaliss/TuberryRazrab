from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampedModel


class AuditLog(TimestampedModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    scope: str
    action: str
    details: Optional[str] = None
