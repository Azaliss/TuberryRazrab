import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot import Bot


class BotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_client(self, client_id: int) -> list[Bot]:
        result = await self.session.execute(select(Bot).where(Bot.client_id == client_id))
        return list(result.scalars().all())

    async def get(self, bot_id: int) -> Bot | None:
        result = await self.session.execute(select(Bot).where(Bot.id == bot_id))
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Bot | None:
        result = await self.session.execute(select(Bot).where(Bot.token == token).limit(1))
        return result.scalar_one_or_none()

    async def create(
        self,
        client_id: int,
        token: str,
        bot_username: str | None = None,
        group_chat_id: str | None = None,
        topic_mode: bool = True,
    ) -> Bot:
        bot = Bot(
            client_id=client_id,
            token=token,
            bot_username=bot_username,
            group_chat_id=group_chat_id,
            topic_mode=topic_mode,
            webhook_secret=secrets.token_urlsafe(16),
        )
        self.session.add(bot)
        await self.session.commit()
        await self.session.refresh(bot)
        return bot

    async def update(self, bot: Bot, **kwargs) -> Bot:
        for key, value in kwargs.items():
            if value is not None and hasattr(bot, key):
                setattr(bot, key, value)
        from datetime import datetime

        bot.updated_at = datetime.utcnow()
        if not bot.webhook_secret:
            import secrets

            bot.webhook_secret = secrets.token_urlsafe(16)
        await self.session.commit()
        await self.session.refresh(bot)
        return bot

    async def delete(self, bot: Bot) -> None:
        await self.session.delete(bot)
        await self.session.commit()
