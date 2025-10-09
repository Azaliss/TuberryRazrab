from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class TelegramLinkRequest(BaseModel):
    telegram_user_id: str
    role: str = "manager"


class TelegramLinkResponse(BaseModel):
    link_token: str


class TelegramLinkExchangeRequest(BaseModel):
    token: str
    email: EmailStr
    full_name: str | None = None


class TelegramLinkExchangeResponse(BaseModel):
    access_token: str
    client_created: bool


class TelegramAuthRequest(BaseModel):
    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    language_code: str | None = None
    allows_write_to_pm: bool | None = None


class AdminPasswordLoginRequest(BaseModel):
    username: str
    password: str
