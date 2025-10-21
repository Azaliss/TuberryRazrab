from app.schemas.auth import (
    BootstrapAdminRequest,
    LoginRequest,
    TelegramLinkExchangeRequest,
    TelegramLinkExchangeResponse,
    TelegramLinkRequest,
    TelegramLinkResponse,
    TokenResponse,
)
from app.schemas.client import ClientCreateRequest, ClientResponse, ClientUpdateRequest
from app.schemas.bot import BotCreateRequest, BotResponse, BotUpdateRequest
from app.schemas.avito import AvitoAccountCreateRequest, AvitoAccountResponse, AvitoAccountUpdateRequest
from app.schemas.dialog import DialogMessagesResponse, DialogResponse
from app.schemas.telegram_source import (
    TelegramSourceCreateRequest,
    TelegramSourceResponse,
    TelegramSourceUpdateRequest,
)

__all__ = [
    "BootstrapAdminRequest",
    "LoginRequest",
    "TelegramLinkExchangeRequest",
    "TelegramLinkExchangeResponse",
    "TelegramLinkRequest",
    "TelegramLinkResponse",
    "TokenResponse",
    "ClientCreateRequest",
    "ClientResponse",
    "ClientUpdateRequest",
    "BotCreateRequest",
    "BotResponse",
    "BotUpdateRequest",
    "AvitoAccountCreateRequest",
    "AvitoAccountResponse",
    "AvitoAccountUpdateRequest",
    "DialogMessagesResponse",
    "DialogResponse",
    "TelegramSourceCreateRequest",
    "TelegramSourceResponse",
    "TelegramSourceUpdateRequest",
]
