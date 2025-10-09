import json
from collections.abc import Sequence

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.enums import MessageDirection


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        dialog_id: int,
        direction: str,
        source_message_id: str | None,
        body: str,
        attachments: str | dict | Sequence | None = None,
        status: str = "pending",
        telegram_message_id: str | None = None,
        is_auto_reply: bool = False,
        is_client_message: bool = False,
    ) -> Message:
        message = Message(
            dialog_id=dialog_id,
            direction=direction,
            source_message_id=source_message_id,
            body=body,
            attachments=self._serialize_attachments(attachments),
            status=status,
            telegram_message_id=telegram_message_id,
            is_auto_reply=is_auto_reply,
            is_client_message=is_client_message,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    def _serialize_attachments(self, attachments: str | dict | Sequence | None) -> str | None:
        if attachments is None:
            return None
        if isinstance(attachments, str):
            return attachments
        try:
            return json.dumps(attachments, ensure_ascii=False)
        except TypeError:
            raise TypeError("attachments must be JSON-serializable")

    async def list_for_dialog(self, dialog_id: int) -> list[Message]:
        result = await self.session.execute(select(Message).where(Message.dialog_id == dialog_id))
        return list(result.scalars().all())

    async def get_by_source(self, *, direction: str, source_message_id: str) -> Message | None:
        query = (
            select(Message)
            .where(
                Message.direction == direction,
                Message.source_message_id == source_message_id,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_telegram(
        self,
        *,
        telegram_message_id: str,
        direction: str | None = None,
    ) -> Message | None:
        query = select(Message).where(Message.telegram_message_id == telegram_message_id)
        if direction is not None:
            query = query.where(Message.direction == direction)
        query = query.order_by(Message.id.desc()).limit(2)
        result = await self.session.execute(query)
        rows = result.scalars().all()
        if not rows:
            return None
        if len(rows) > 1:
            # Prefer matching direction == avito if available to disambiguate duplicates produced earlier
            for row in rows:
                if direction is not None and row.direction == direction:
                    return row
                if direction is None and row.is_client_message:
                    return row
        return rows[0]

    async def delete_for_dialogs(self, dialog_ids: list[int]) -> None:
        if not dialog_ids:
            return
        await self.session.execute(delete(Message).where(Message.dialog_id.in_(dialog_ids)))

    async def get_last_by_direction(self, dialog_id: int, direction: MessageDirection) -> Message | None:
        result = await self.session.execute(
            select(Message)
                .where(Message.dialog_id == dialog_id, Message.direction == direction)
                .order_by(Message.created_at.desc())
                .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_outgoing_since(self, dialog_id: int, since: datetime) -> bool:
        result = await self.session.execute(
            select(Message.id)
                .where(
                    Message.dialog_id == dialog_id,
                    Message.direction == MessageDirection.telegram,
                    Message.is_auto_reply.is_(False),
                    Message.created_at >= since,
                )
                .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def mark_as_client_message(self, message: Message) -> Message:
        if message.is_client_message:
            return message
        message.is_client_message = True
        message.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def mark_status(self, message_id: int, status: str) -> None:
        await self.session.execute(
            update(Message)
            .where(Message.id == message_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.commit()
