import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_source import TelegramSource
from app.models.enums import TelegramSourceStatus


class TelegramSourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_client(self, client_id: int) -> list[TelegramSource]:
        result = await self.session.execute(select(TelegramSource).where(TelegramSource.client_id == client_id))
        return list(result.scalars().all())

    async def get(self, source_id: int) -> TelegramSource | None:
        result = await self.session.execute(select(TelegramSource).where(TelegramSource.id == source_id))
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> TelegramSource | None:
        result = await self.session.execute(select(TelegramSource).where(TelegramSource.token == token).limit(1))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        client_id: int,
        bot_id: int,
        token: str,
        bot_username: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TelegramSource:
        source = TelegramSource(
            client_id=client_id,
            bot_id=bot_id,
            token=token,
            bot_username=bot_username,
            display_name=display_name,
            description=description,
            status=TelegramSourceStatus.inactive,
            webhook_secret=secrets.token_urlsafe(16),
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update(self, source: TelegramSource, **kwargs) -> TelegramSource:
        for key, value in kwargs.items():
            if hasattr(source, key) and value is not None:
                setattr(source, key, value)
        from datetime import datetime

        source.updated_at = datetime.utcnow()
        if not source.webhook_secret:
            source.webhook_secret = secrets.token_urlsafe(16)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete(self, source: TelegramSource) -> None:
        await self.session.delete(source)
        await self.session.commit()
