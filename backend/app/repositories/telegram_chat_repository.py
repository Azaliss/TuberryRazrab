from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_chat import TelegramChat


class TelegramChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, *, bot_id: int, chat_id: str) -> TelegramChat | None:
        result = await self.session.execute(
            select(TelegramChat).where(
                TelegramChat.bot_id == bot_id,
                TelegramChat.chat_id == chat_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_membership(
        self,
        *,
        bot_id: int,
        chat_id: str,
        title: str | None,
        chat_type: str | None,
        username: str | None,
        is_forum: bool | None,
        status: str | None,
        is_member: bool,
    ) -> TelegramChat:
        chat = await self.get(bot_id=bot_id, chat_id=chat_id)
        now = datetime.utcnow()

        if chat is None:
            chat = TelegramChat(
                bot_id=bot_id,
                chat_id=chat_id,
                title=title,
                chat_type=chat_type,
                username=username,
                is_forum=is_forum,
                is_active=is_member,
                last_status=status,
                joined_at=now if is_member else None,
                left_at=None,
                updated_at=now,
            )
            self.session.add(chat)
        else:
            if title:
                chat.title = title
            chat.chat_type = chat_type or chat.chat_type
            chat.username = username or chat.username
            chat.is_forum = is_forum if is_forum is not None else chat.is_forum
            chat.last_status = status or chat.last_status
            if is_member:
                if not chat.is_active:
                    chat.joined_at = now
                    chat.left_at = None
                chat.is_active = True
            else:
                if chat.is_active:
                    chat.left_at = now
                chat.is_active = False
            chat.updated_at = now

        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def list_active_for_bot(self, bot_id: int) -> list[TelegramChat]:
        result = await self.session.execute(
            select(TelegramChat)
            .where(TelegramChat.bot_id == bot_id, TelegramChat.is_active.is_(True))
            .order_by(TelegramChat.title.asc(), TelegramChat.chat_id.asc())
        )
        return list(result.scalars().all())

    async def update_chat(self, chat: TelegramChat, **changes: object) -> TelegramChat:
        for key, value in changes.items():
            if hasattr(chat, key) and value is not None:
                setattr(chat, key, value)
        chat.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(chat)
        return chat
