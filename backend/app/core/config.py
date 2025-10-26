from functools import lru_cache
from typing import List, Tuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PERSONAL_TELEGRAM_API_ID = 6
DEFAULT_PERSONAL_TELEGRAM_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
DEFAULT_PERSONAL_TELEGRAM_DEVICE_MODEL = "Samsung Galaxy S24 Ultra"
DEFAULT_PERSONAL_TELEGRAM_SYSTEM_VERSION = "Android 14 (API 34)"
DEFAULT_PERSONAL_TELEGRAM_APP_VERSION = "10.6.0-release"
DEFAULT_PERSONAL_TELEGRAM_LANG_CODE = "ru"


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "supersecret"
    jwt_secret: str = "changeme"
    jwt_expires: int = 3600
    database_url: str = "sqlite+aiosqlite:///./tuberry.db"
    redis_url: str = "redis://localhost:6379/0"

    master_bot_token: str = ""
    master_bot_name: str = ""
    telegram_api_base: str = "https://api.telegram.org"

    avito_api_base: str = "https://api.avito.ru"
    avito_client_id: str = ""
    avito_client_secret: str = ""
    avito_poller_interval: int = 30
    avito_poller_mark_read: bool = True

    webhook_base_url: str = "http://localhost:8080"
    backend_internal_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    avito_webhook_events: List[str] = ["message"]

    personal_telegram_api_id: int | None = None
    personal_telegram_api_hash: str | None = None
    personal_telegram_session_secret: str | None = None
    personal_telegram_qr_timeout: int = 180
    personal_telegram_device_model: str = DEFAULT_PERSONAL_TELEGRAM_DEVICE_MODEL
    personal_telegram_system_version: str = DEFAULT_PERSONAL_TELEGRAM_SYSTEM_VERSION
    personal_telegram_app_version: str = DEFAULT_PERSONAL_TELEGRAM_APP_VERSION
    personal_telegram_lang_code: str = DEFAULT_PERSONAL_TELEGRAM_LANG_CODE
    personal_telegram_system_lang_code: str | None = None

    admin_basic_username: str = "admin"
    admin_basic_password: str = "30080724"
    admin_account_email: str = "admin@tuberry.local"
    admin_account_name: str = "Tuberry Admin"

    cors_origins: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @field_validator("personal_telegram_api_id", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    def get_personal_telegram_credentials(self) -> Tuple[int, str]:
        api_id = self.personal_telegram_api_id or DEFAULT_PERSONAL_TELEGRAM_API_ID
        api_hash = self.personal_telegram_api_hash or DEFAULT_PERSONAL_TELEGRAM_API_HASH
        return int(api_id), api_hash

    def get_personal_telegram_device_info(self) -> dict[str, str]:
        system_lang_code = (
            self.personal_telegram_system_lang_code or self.personal_telegram_lang_code or DEFAULT_PERSONAL_TELEGRAM_LANG_CODE
        )
        return {
            "device_model": self.personal_telegram_device_model or DEFAULT_PERSONAL_TELEGRAM_DEVICE_MODEL,
            "system_version": self.personal_telegram_system_version or DEFAULT_PERSONAL_TELEGRAM_SYSTEM_VERSION,
            "app_version": self.personal_telegram_app_version or DEFAULT_PERSONAL_TELEGRAM_APP_VERSION,
            "lang_code": self.personal_telegram_lang_code or DEFAULT_PERSONAL_TELEGRAM_LANG_CODE,
            "system_lang_code": system_lang_code,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
