from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    admin_basic_username: str = "admin"
    admin_basic_password: str = "30080724"
    admin_account_email: str = "admin@tuberry.local"
    admin_account_name: str = "Tuberry Admin"

    cors_origins: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
