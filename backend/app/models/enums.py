from enum import Enum


class UserRole(str, Enum):
    owner = "owner"
    manager = "manager"
    admin = "admin"


class BotStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class TelegramSourceStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class PersonalTelegramAccountStatus(str, Enum):
    pending = "pending"
    active = "active"
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
    telegram_source_in = "telegram_source_in"
    telegram_source_out = "telegram_source_out"
    personal_telegram_in = "personal_telegram_in"
    personal_telegram_out = "personal_telegram_out"


class MessageStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class AutoReplyMode(str, Enum):
    always = "always"
    first = "first"


class DialogSource(str, Enum):
    avito = "avito"
    telegram = "telegram"
    personal_telegram = "personal_telegram"
