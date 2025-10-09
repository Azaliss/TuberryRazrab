from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avito import AvitoAccount


class AvitoAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_client(self, client_id: int) -> list[AvitoAccount]:
        result = await self.session.execute(select(AvitoAccount).where(AvitoAccount.client_id == client_id))
        return list(result.scalars().all())

    async def get(self, account_id: int) -> AvitoAccount | None:
        result = await self.session.execute(select(AvitoAccount).where(AvitoAccount.id == account_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        client_id: int,
        api_client_id: str,
        api_client_secret: str,
        name: str | None = None,
        access_token: str | None = None,
        expires_at: datetime | None = None,
        bot_id: int | None = None,
        monitoring_enabled: bool = True,
    ) -> AvitoAccount:
        account = AvitoAccount(
            client_id=client_id,
            name=name,
            api_client_id=api_client_id,
            api_client_secret=api_client_secret,
            access_token=access_token,
            token_expires_at=expires_at,
            bot_id=bot_id,
            monitoring_enabled=monitoring_enabled,
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(self, account: AvitoAccount, **kwargs) -> AvitoAccount:
        for key, value in kwargs.items():
            if hasattr(account, key):
                setattr(account, key, value)
        from datetime import datetime

        account.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def list_by_bot(self, bot_id: int) -> list[AvitoAccount]:
        result = await self.session.execute(select(AvitoAccount).where(AvitoAccount.bot_id == bot_id))
        return list(result.scalars().all())

    async def delete(self, account: AvitoAccount) -> None:
        await self.session.delete(account)
        await self.session.commit()
