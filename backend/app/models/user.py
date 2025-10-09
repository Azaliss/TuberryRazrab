from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampedModel
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.client import Client


class User(TimestampedModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    telegram_user_id: Optional[str] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None, index=True)
    full_name: Optional[str] = None
    role: UserRole = Field(default=UserRole.manager)
    hashed_password: Optional[str] = None
    is_active: bool = Field(default=True)

    client: Optional["Client"] = Relationship(back_populates="users")


class UserCreate(SQLModel):
    email: Optional[str]
    full_name: Optional[str]
    role: UserRole = UserRole.manager
    password: Optional[str]
    telegram_user_id: Optional[str]
