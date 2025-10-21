from __future__ import annotations

import logging
from html import escape
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bot import Bot
from app.models.dialog import Dialog
from app.models.enums import DialogSource, MessageDirection, MessageStatus, TelegramSourceStatus
from app.models.telegram_source import TelegramSource
from app.repositories.bot_repository import BotRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.telegram_source_repository import TelegramSourceRepository
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)


class TelegramSourceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dialog_repo = DialogRepository(session)
        self.message_repo = MessageRepository(session)
        self.bot_repo = BotRepository(session)
        self.source_repo = TelegramSourceRepository(session)

    def build_webhook_url(self, source: TelegramSource) -> Optional[str]:
        base_url = settings.webhook_base_url
        if not base_url or not source.webhook_secret:
            return None
        return f"{base_url.rstrip('/')}/api/webhooks/source-telegram/{source.id}/{source.webhook_secret}"

    async def ensure_webhook(self, source: TelegramSource) -> None:
        url = self.build_webhook_url(source)
        if not url:
            raise ValueError("WEBHOOK_BASE_URL или webhook_secret не настроены для Telegram источника")
        service = TelegramService(source.token)
        await service.set_webhook(
            url,
            secret_token=source.webhook_secret,
            allowed_updates=["message", "channel_post"],
            drop_pending_updates=True,
        )
        if source.status != TelegramSourceStatus.active:
            await self.source_repo.update(source, status=TelegramSourceStatus.active)

    async def delete_webhook(self, source: TelegramSource, *, drop_pending_updates: bool = False) -> None:
        service = TelegramService(source.token)
        try:
            await service.delete_webhook(drop_pending_updates=drop_pending_updates)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete webhook for Telegram source %s: %s", source.id, exc)

    async def handle_incoming_update(
        self,
        *,
        source: TelegramSource,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        message = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
        )
        if not message:
            return {"status": "ignored", "reason": "no_message"}

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return {"status": "ignored", "reason": "missing_chat_id"}
        message_id = message.get("message_id")

        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return {"status": "ignored", "reason": "bot_event"}

        controller_bot = await self.bot_repo.get(source.bot_id)
        if controller_bot is None:
            raise ValueError("Управляющий бот для Telegram источника не найден")
        if not controller_bot.group_chat_id:
            raise ValueError("Для управляющего бота не настроен рабочий чат")

        target_chat_id = controller_bot.group_chat_id
        manager_service = TelegramService(controller_bot.token)
        source_service = TelegramService(source.token)

        display_name = self._build_display_name(sender)
        username = sender.get("username")
        external_reference = str(chat_id)

        dialog = await self.dialog_repo.get_by_telegram_source(
            telegram_source_id=source.id,
            external_reference=external_reference,
        )

        topic_id: Optional[str] = dialog.telegram_topic_id if dialog else None
        created_dialog = False

        if dialog is None:
            topic_id = await self._create_topic_if_needed(
                manager_service=manager_service,
                bot=controller_bot,
                target_chat_id=target_chat_id,
                client_label=display_name or username or external_reference,
            )
            dialog = await self.dialog_repo.create(
                client_id=source.client_id,
                bot_id=controller_bot.id,
                avito_dialog_id=f"tg:{source.id}:{external_reference}",
                avito_account_id=None,
                source=DialogSource.telegram,
                telegram_chat_id=target_chat_id,
                telegram_topic_id=topic_id,
                telegram_source_id=source.id,
                external_reference=external_reference,
                external_display_name=display_name,
                external_username=username,
            )
            created_dialog = True
            await self._send_intro_message(
                manager_service=manager_service,
                dialog=dialog,
                bot=controller_bot,
                source=source,
                display_name=display_name,
                username=username,
                external_reference=external_reference,
            )

        thread_id_int = self._normalize_topic_id(dialog.telegram_topic_id)

        updates_performed = False
        if display_name and display_name != dialog.external_display_name:
            dialog.external_display_name = display_name
            updates_performed = True
        if username and username != dialog.external_username:
            dialog.external_username = username
            updates_performed = True
        if not dialog.telegram_chat_id:
            dialog.telegram_chat_id = target_chat_id
            updates_performed = True
        if updates_performed:
            await self.session.commit()
            await self.session.refresh(dialog)

        text_value = message.get("text")
        caption_value = message.get("caption")
        photos = message.get("photo") or []

        client_label = display_name or username or external_reference
        attachments_records: list[dict[str, Any]] = []
        manager_message_ids: list[str] = []

        if text_value:
            rendered = f"💬 <b>{escape(client_label)}</b>\n{escape(text_value)}"
            result = await manager_service.send_message(
                chat_id=target_chat_id,
                text=rendered,
                message_thread_id=thread_id_int,
            )
            manager_message_id = result.get("message_id")
            if manager_message_id is not None:
                manager_message_ids.append(str(manager_message_id))

        if photos:
            best_photo = self._select_best_photo(photos)
            file_id = best_photo.get("file_id")
            if file_id:
                file_bytes, filename, content_type = await source_service.download_file(file_id)
                caption_text = caption_value or ""
                if caption_text:
                    caption_prepared = f"📷 <b>{escape(client_label)}</b>\n{escape(caption_text)}"
                else:
                    caption_prepared = f"📷 <b>{escape(client_label)}</b> отправил(а) фотографию"

                result = await manager_service.send_photo(
                    chat_id=target_chat_id,
                    photo=(file_bytes, filename or "photo.jpg", content_type),
                    caption=caption_prepared,
                    message_thread_id=thread_id_int,
                )
                manager_message_id = result.get("message_id")
                if manager_message_id is not None:
                    manager_message_ids.append(str(manager_message_id))
                attachments_records.append(
                    {
                        "type": "photo",
                        "file_id": file_id,
                        "width": best_photo.get("width"),
                        "height": best_photo.get("height"),
                    }
                )
        elif caption_value and not text_value:
            rendered = f"💬 <b>{escape(client_label)}</b>\n{escape(caption_value)}"
            result = await manager_service.send_message(
                chat_id=target_chat_id,
                text=rendered,
                message_thread_id=thread_id_int,
            )
            manager_message_id = result.get("message_id")
            if manager_message_id is not None:
                manager_message_ids.append(str(manager_message_id))

        body_value = text_value or caption_value or "[telegram message]"

        stored_message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.telegram.value,
            source_message_id=str(message_id) if message_id is not None else None,
            body=body_value,
            attachments=attachments_records if attachments_records else None,
            status=MessageStatus.delivered.value,
            telegram_message_id=manager_message_ids[0] if manager_message_ids else None,
            is_client_message=True,
        )

        await self.dialog_repo.touch(dialog)

        status_details = {
            "status": "stored",
            "dialog_id": dialog.id,
            "message_id": stored_message.id,
            "created_dialog": created_dialog,
        }
        return status_details

    async def handle_manager_reply(
        self,
        *,
        dialog: Dialog,
        bot: Bot,
        telegram_message: Dict[str, Any],
        message_id: Optional[str],
    ) -> Dict[str, Any]:
        if dialog.telegram_source_id is None:
            raise ValueError("Диалог не связан с Telegram источником")
        source = await self.source_repo.get(dialog.telegram_source_id)
        if source is None:
            raise ValueError("Telegram источник не найден")
        if dialog.external_reference is None:
            raise ValueError("Отсутствует идентификатор получателя Telegram")

        user_chat_id = dialog.external_reference
        user_service = TelegramService(source.token)
        manager_service = TelegramService(bot.token)

        text_value = telegram_message.get("text")
        caption_value = telegram_message.get("caption")
        photos = telegram_message.get("photo") or []

        attachments_records: list[dict[str, Any]] = []

        if photos:
            best_photo = self._select_best_photo(photos)
            file_id = best_photo.get("file_id")
            if file_id:
                file_bytes, filename, content_type = await manager_service.download_file(file_id)
                photo_caption = caption_value or ""
                await user_service.send_photo(
                    chat_id=user_chat_id,
                    photo=(file_bytes, filename or "photo.jpg", content_type),
                    caption=self._escape_text(photo_caption) if photo_caption else None,
                    message_thread_id=None,
                )
                attachments_records.append(
                    {
                        "type": "photo",
                        "file_id": file_id,
                        "width": best_photo.get("width"),
                        "height": best_photo.get("height"),
                    }
                )

        message_sent = False
        if text_value:
            await user_service.send_message(
                chat_id=user_chat_id,
                text=self._escape_text(text_value),
            )
            message_sent = True
        elif not photos and caption_value:
            await user_service.send_message(
                chat_id=user_chat_id,
                text=self._escape_text(caption_value),
            )
            message_sent = True
        elif not photos and not text_value and not caption_value:
            raise ValueError("Невозможно отправить пустое сообщение пользователю Telegram")

        body_value = text_value or caption_value or "[telegram message]"

        stored_message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.telegram.value,
            source_message_id=message_id,
            body=body_value,
            attachments=attachments_records if attachments_records else None,
            status=MessageStatus.sent.value,
            telegram_message_id=message_id,
        )

        await self.dialog_repo.touch(dialog)

        if source.status != TelegramSourceStatus.active:
            await self.source_repo.update(source, status=TelegramSourceStatus.active)

        return {
            "status": "sent",
            "dialog_id": dialog.id,
            "message_db_id": stored_message.id,
            "message_sent": message_sent or bool(photos),
        }

    async def _send_intro_message(
        self,
        *,
        manager_service: TelegramService,
        dialog: Dialog,
        bot: Bot,
        source: TelegramSource,
        display_name: Optional[str],
        username: Optional[str],
        external_reference: str,
    ) -> None:
        thread_id_int = self._normalize_topic_id(dialog.telegram_topic_id)
        label = display_name or username or external_reference
        parts = [
            "🆕 <b>Новый диалог из Telegram</b>",
            f"Источник: {escape(source.display_name or source.bot_username or 'без названия')}",
            f"Пользователь: <b>{escape(label)}</b>",
        ]
        if username:
            parts.append(f"@{escape(username)}")
        parts.append(f"ID: <code>{escape(external_reference)}</code>")
        try:
            await manager_service.send_message(
                chat_id=bot.group_chat_id,
                text="\n".join(parts),
                message_thread_id=thread_id_int,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить вступительное сообщение по диалогу %s: %s", dialog.id, exc)

    async def _create_topic_if_needed(
        self,
        *,
        manager_service: TelegramService,
        bot: Bot,
        target_chat_id: str,
        client_label: str,
    ) -> Optional[str]:
        if not bot.topic_mode:
            return None
        try:
            result = await manager_service.create_topic(target_chat_id, f"ТГ - {client_label}"[:128])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось создать топик в Telegram для клиента %s: %s", client_label, exc)
            return None
        topic_id = (
            result.get("message_thread_id")
            or result.get("forum_topic_id")
            or result.get("topic", {}).get("message_thread_id")
        )
        return str(topic_id) if topic_id is not None else None

    @staticmethod
    def _select_best_photo(photos: list[dict[str, Any]]) -> dict[str, Any]:
        if not photos:
            return {}
        return max(photos, key=lambda item: item.get("file_size", 0) or 0)

    @staticmethod
    def _normalize_topic_id(topic_id: Optional[str]) -> Optional[int]:
        if topic_id is None:
            return None
        try:
            return int(topic_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_display_name(sender: Dict[str, Any]) -> Optional[str]:
        first_name = sender.get("first_name")
        last_name = sender.get("last_name")
        if first_name and last_name:
            return f"{first_name} {last_name}".strip()
        if first_name:
            return first_name
        return last_name

    @staticmethod
    def _escape_text(value: str) -> str:
        return escape(value) if value else value
