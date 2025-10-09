from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client


class ClientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        plan: str = "default",
        filter_keywords: str | None = None,
        require_reply_for_avito: bool = False,
        hide_system_messages: bool = True,
        auto_reply_enabled: bool = False,
        auto_reply_always: bool = False,
        auto_reply_start_time=None,
        auto_reply_end_time=None,
        auto_reply_timezone: str | None = None,
        auto_reply_text: str | None = None,
    ) -> Client:
        client = Client(
            name=name,
            plan=plan,
            filter_keywords=filter_keywords,
            require_reply_for_avito=require_reply_for_avito,
            hide_system_messages=hide_system_messages,
            auto_reply_enabled=auto_reply_enabled,
            auto_reply_always=auto_reply_always,
            auto_reply_start_time=auto_reply_start_time,
            auto_reply_end_time=auto_reply_end_time,
            auto_reply_timezone=auto_reply_timezone,
            auto_reply_text=auto_reply_text,
        )
        self.session.add(client)
        await self.session.commit()
        await self.session.refresh(client)
        return client

    async def update(self, client: Client, **kwargs) -> Client:
        for key, value in kwargs.items():
            if hasattr(client, key):
                setattr(client, key, value)
        from datetime import datetime

        client.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(client)
        return client

    async def get_by_id(self, client_id: int) -> Client | None:
        result = await self.session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Client]:
        result = await self.session.execute(select(Client))
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Client | None:
        result = await self.session.execute(select(Client).where(Client.name == name))
        return result.scalar_one_or_none()
