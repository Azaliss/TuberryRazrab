from enum import Enum


class UserRole(str, Enum):
    owner = "owner"
    manager = "manager"
    admin = "admin"


class BotStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class AvitoAccountStatus(str, Enum):
    active = "active"
    expired = "expired"
    blocked = "blocked"


class DialogState(str, Enum):
    active = "active"
    closed = "closed"


class MessageDirection(str, Enum):
    avito = "avito"
    telegram = "telegram"


class MessageStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class AutoReplyMode(str, Enum):
    always = "always"
    first = "first"
