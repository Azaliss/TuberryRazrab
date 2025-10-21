from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dialog import Dialog
from app.models.enums import DialogSource


class DialogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_avito(self, client_id: int, avito_dialog_id: str) -> Dialog | None:
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.client_id == client_id,
                Dialog.avito_dialog_id == avito_dialog_id,
                Dialog.source == DialogSource.avito.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_topic(self, bot_id: int, topic_id: str) -> Dialog | None:
        result = await self.session.execute(
            select(Dialog).where(Dialog.bot_id == bot_id, Dialog.telegram_topic_id == topic_id)
        )
        return result.scalar_one_or_none()

    async def list_for_client(self, client_id: int) -> list[Dialog]:
        result = await self.session.execute(select(Dialog).where(Dialog.client_id == client_id))
        return list(result.scalars().all())

    async def get(self, dialog_id: int) -> Dialog | None:
        result = await self.session.execute(select(Dialog).where(Dialog.id == dialog_id))
        return result.scalar_one_or_none()

    async def get_by_account_and_avito_id(self, avito_account_id: int, avito_dialog_id: str) -> Dialog | None:
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.avito_account_id == avito_account_id,
                Dialog.avito_dialog_id == avito_dialog_id,
                Dialog.source == DialogSource.avito.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_avito_account(self, account_id: int) -> list[Dialog]:
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.avito_account_id == account_id,
                Dialog.source == DialogSource.avito.value,
            )
        )
        return list(result.scalars().all())

    async def list_for_bot(self, bot_id: int) -> list[Dialog]:
        result = await self.session.execute(select(Dialog).where(Dialog.bot_id == bot_id))
        return list(result.scalars().all())

    async def get_recent_by_chat(self, bot_id: int, chat_id: str) -> Dialog | None:
        result = await self.session.execute(
            select(Dialog)
            .where(Dialog.bot_id == bot_id, Dialog.telegram_chat_id == chat_id)
            .order_by(Dialog.last_message_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        client_id: int,
        bot_id: int,
        avito_dialog_id: str,
        avito_account_id: int | None = None,
        source: DialogSource = DialogSource.avito,
        telegram_chat_id: str | None,
        telegram_topic_id: str | None,
        telegram_source_id: int | None = None,
        external_reference: str | None = None,
        external_display_name: str | None = None,
        external_username: str | None = None,
    ) -> Dialog:
        dialog = Dialog(
            client_id=client_id,
            avito_account_id=avito_account_id,
            source=source.value if isinstance(source, DialogSource) else source,
            telegram_source_id=telegram_source_id,
            bot_id=bot_id,
            avito_dialog_id=avito_dialog_id,
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            last_message_at=datetime.utcnow(),
            topic_intro_sent=False,
            external_reference=external_reference,
            external_display_name=external_display_name,
            external_username=external_username,
        )
        self.session.add(dialog)
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def get_by_telegram_source(
        self,
        *,
        telegram_source_id: int,
        external_reference: str,
    ) -> Dialog | None:
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.telegram_source_id == telegram_source_id,
                Dialog.external_reference == external_reference,
                Dialog.source == DialogSource.telegram.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_telegram_source(self, telegram_source_id: int) -> list[Dialog]:
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.telegram_source_id == telegram_source_id,
                Dialog.source == DialogSource.telegram.value,
            )
        )
        return list(result.scalars().all())

    async def touch(self, dialog: Dialog) -> Dialog:
        dialog.last_message_at = datetime.utcnow()
        dialog.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def mark_auto_reply_sent(self, dialog: Dialog, timestamp: datetime) -> Dialog:
        dialog.auto_reply_last_sent_at = timestamp
        dialog.auto_reply_scheduled_at = None
        dialog.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def set_auto_reply_schedule(self, dialog: Dialog, scheduled_at: datetime | None) -> Dialog:
        dialog.auto_reply_scheduled_at = scheduled_at
        dialog.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def clear_auto_reply_schedule(self, dialog: Dialog) -> Dialog:
        if dialog.auto_reply_scheduled_at is None:
            return dialog
        dialog.auto_reply_scheduled_at = None
        dialog.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def reset_auto_reply_marks_for_client(self, client_id: int) -> None:
        await self.session.execute(
            update(Dialog)
            .where(Dialog.client_id == client_id)
            .values(
                auto_reply_last_sent_at=None,
                auto_reply_scheduled_at=None,
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.commit()

    async def set_topic(self, dialog: Dialog, topic_id: str | None) -> Dialog:
        dialog.telegram_topic_id = topic_id
        if topic_id:
            dialog.topic_intro_sent = False
        dialog.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def delete(self, dialog: Dialog) -> None:
        await self.session.delete(dialog)
        await self.session.commit()
