from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import settings
from app.models import telegram_chat  # noqa: F401

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        if "postgresql" in settings.database_url:
            await conn.execute(
                text(
                    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS require_reply_for_avito BOOLEAN DEFAULT FALSE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS telegram_message_id VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS topic_intro_sent BOOLEAN DEFAULT FALSE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS hide_system_messages BOOLEAN DEFAULT TRUE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS auto_reply_scheduled_at TIMESTAMP"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_client_message BOOLEAN DEFAULT FALSE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE avito_accounts ADD COLUMN IF NOT EXISTS webhook_secret VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE avito_accounts ADD COLUMN IF NOT EXISTS webhook_url VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE avito_accounts ADD COLUMN IF NOT EXISTS webhook_enabled BOOLEAN DEFAULT FALSE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE avito_accounts ADD COLUMN IF NOT EXISTS webhook_last_error TEXT"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ALTER COLUMN avito_account_id DROP NOT NULL"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'avito'"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS telegram_source_id INTEGER"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS external_reference VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS external_display_name VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS external_username VARCHAR"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS project_id INTEGER"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE avito_accounts ADD COLUMN IF NOT EXISTS project_id INTEGER"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE telegram_sources ADD COLUMN IF NOT EXISTS project_id INTEGER"
                )
            )
