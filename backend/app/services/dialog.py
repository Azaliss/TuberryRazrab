from __future__ import annotations

import logging
import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from html import escape
from typing import Any, Awaitable, Callable, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot import Bot
from app.models.dialog import Dialog
from app.models.enums import BotStatus, DialogSource, MessageDirection, MessageStatus
from app.db.session import SessionLocal
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.bot_repository import BotRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.client_repository import ClientRepository
from app.services.avito import AvitoService
from app.services.telegram import TelegramService
from app.services.queue import TaskQueue


logger = logging.getLogger(__name__)

AUTO_REPLY_DELAY_SECONDS = 75


@dataclass
class DialogContext:
    bot: Bot
    dialog: Dialog
    tg: TelegramService
    telegram_chat_id: Optional[str]
    telegram_topic_id: Optional[str]
    target_chat_id: str
    item_title: Optional[str]
    item_url: Optional[str]
    item_city: Optional[str]
    item_price: Optional[str]
    avito_account: Any
    created: bool
    topic_intro_sent: bool


class DialogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dialog_repo = DialogRepository(session)
        self.message_repo = MessageRepository(session)
        self.bot_repo = BotRepository(session)
        self.avito_repo = AvitoAccountRepository(session)
        self.client_repo = ClientRepository(session)
        self.avito_service = AvitoService()

    async def handle_avito_message(
        self,
        *,
        client_id: int,
        avito_account_id: int,
        avito_dialog_id: str,
        message_text: str | None,
        sender: Optional[str] = None,
        item_title: Optional[str] = None,
        source_message_id: Optional[str] = None,
        attachments: Sequence[dict[str, Any]] | None = None,
        message_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        text_value = message_text or ""
        normalized_attachments = list(attachments or [])

        client = await self.client_repo.get_by_id(client_id)

        if text_value:
            if await self._should_ignore_message(client_id=client_id, message_text=text_value, client=client):
                logger.info("Ignoring Avito message for client %s due to filter", client_id)
                return {"ignored": True, "reason": "filtered"}

        if not text_value and not normalized_attachments:
            logger.info(
                "Ignoring Avito message for client %s dialog %s due to empty payload",
                client_id,
                avito_dialog_id,
            )
            return {"ignored": True, "reason": "empty"}

        if source_message_id:
            existing = await self.message_repo.get_by_source(
                direction=MessageDirection.avito.value,
                source_message_id=source_message_id,
            )
            if existing:
                return {"ignored": True, "reason": "duplicate"}

        context = await self._ensure_dialog_context(
            client_id=client_id,
            avito_account_id=avito_account_id,
            avito_dialog_id=avito_dialog_id,
            sender=sender,
            item_title=item_title,
            client=client,
        )
        dialog = context.dialog
        telegram_results: list[Dict[str, Any]] = []
        telegram_message_ids: list[str] = []
        attachments_records: list[dict[str, Any]] = []

        remaining_text_for_caption: Optional[str] = text_value or None

        for attachment in normalized_attachments:
            kind = str(attachment.get("type") or message_type or "").lower()

            if kind == "image":
                photo_url = self._resolve_avito_image_url(attachment)
                if not photo_url:
                    attachments_records.append(
                        {
                            "type": "image",
                            "delivered": False,
                            "reason": "no_url",
                            "payload": attachment,
                        }
                    )
                    continue

                caption = remaining_text_for_caption

                async def _send_photo(thread_id: Optional[int], *, url: str = photo_url, cap: Optional[str] = caption) -> Dict[str, Any]:
                    return await context.tg.send_photo(
                        chat_id=context.target_chat_id,
                        photo=url,
                        caption=cap,
                        message_thread_id=thread_id,
                    )

                send_result, dialog = await self._send_with_topic_recovery(
                    context.tg,
                    chat_id=context.target_chat_id,
                    telegram_topic_id=dialog.telegram_topic_id,
                    bot=context.bot,
                    dialog=dialog,
                    item_title=context.item_title,
                    item_url=context.item_url,
                    item_city=context.item_city,
                    item_price=context.item_price,
                    sender=sender,
                    account_name=context.avito_account.name,
                    telegram_chat_id=context.telegram_chat_id,
                    send_func=_send_photo,
                )

                attachments_records.append(
                    {
                        "type": "image",
                        "delivered": True,
                        "url": photo_url,
                        "payload": attachment,
                    }
                )

                message_id = self._extract_telegram_message_id(send_result)
                if message_id:
                    telegram_message_ids.append(message_id)
                    attachments_records[-1]["telegram_message_id"] = message_id

                telegram_results.append(send_result)
                remaining_text_for_caption = None
                context.dialog = dialog
                context.telegram_topic_id = dialog.telegram_topic_id
                continue

            if kind == "voice":
                voice_id = attachment.get("voice_id") or attachment.get("id")
                if not voice_id:
                    attachments_records.append(
                        {
                            "type": "voice",
                            "delivered": False,
                            "reason": "missing_voice_id",
                            "payload": attachment,
                        }
                    )
                    continue

                voice_urls = await self.avito_service.get_voice_file_urls(avito_account_id, [str(voice_id)])
                voice_url = voice_urls.get(str(voice_id))
                if not voice_url:
                    attachments_records.append(
                        {
                            "type": "voice",
                            "delivered": False,
                            "reason": "no_url",
                            "payload": attachment,
                        }
                    )
                    continue

                caption = remaining_text_for_caption

                voice_bytes, voice_filename, voice_content_type = await self._download_media(voice_url)

                async def _send_voice(
                    thread_id: Optional[int],
                    *,
                    data: bytes = voice_bytes,
                    name: str | None = voice_filename,
                    ctype: str | None = voice_content_type,
                    cap: Optional[str] = caption,
                ) -> Dict[str, Any]:
                    return await context.tg.send_voice(
                        chat_id=context.target_chat_id,
                        voice=(data, name or f"voice_{voice_id}.mp4", ctype),
                        caption=cap,
                        message_thread_id=thread_id,
                    )

                try:
                    send_result, dialog = await self._send_with_topic_recovery(
                        context.tg,
                        chat_id=context.target_chat_id,
                        telegram_topic_id=dialog.telegram_topic_id,
                        bot=context.bot,
                        dialog=dialog,
                        item_title=context.item_title,
                        item_url=context.item_url,
                        item_city=context.item_city,
                        item_price=context.item_price,
                        sender=sender,
                        account_name=context.avito_account.name,
                        telegram_chat_id=context.telegram_chat_id,
                        send_func=_send_voice,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to send voice message via sendVoice, fallback to document: %s",
                        exc,
                    )

                    async def _send_document(
                        thread_id: Optional[int],
                        *,
                        data: bytes = voice_bytes,
                        name: str | None = voice_filename,
                        ctype: str | None = voice_content_type,
                        cap: Optional[str] = caption,
                    ) -> Dict[str, Any]:
                        return await context.tg.send_document(
                            chat_id=context.target_chat_id,
                            document=(data, name or f"voice_{voice_id}.mp4", ctype),
                            caption=cap,
                            message_thread_id=thread_id,
                        )

                    send_result, dialog = await self._send_with_topic_recovery(
                        context.tg,
                        chat_id=context.target_chat_id,
                        telegram_topic_id=dialog.telegram_topic_id,
                        bot=context.bot,
                        dialog=dialog,
                        item_title=context.item_title,
                        item_url=context.item_url,
                        item_city=context.item_city,
                        item_price=context.item_price,
                        sender=sender,
                        account_name=context.avito_account.name,
                        telegram_chat_id=context.telegram_chat_id,
                        send_func=_send_document,
                    )
                    attachments_records.append(
                        {
                            "type": "voice",
                            "delivered": True,
                            "url": voice_url,
                            "payload": attachment,
                            "fallback": "document",
                        }
                    )
                else:
                    attachments_records.append(
                        {
                            "type": "voice",
                            "delivered": True,
                            "url": voice_url,
                            "payload": attachment,
                        }
                    )

                message_id = self._extract_telegram_message_id(send_result)
                if message_id:
                    telegram_message_ids.append(message_id)
                    attachments_records[-1]["telegram_message_id"] = message_id

                telegram_results.append(send_result)
                remaining_text_for_caption = None
                context.dialog = dialog
                context.telegram_topic_id = dialog.telegram_topic_id
                continue

            attachments_records.append(
                {
                    "type": kind or "unknown",
                    "delivered": False,
                    "reason": "unsupported",
                    "payload": attachment,
                }
            )

        if remaining_text_for_caption:
            notification_text = f"💬 Клиент: {remaining_text_for_caption.strip()}"
            send_result, dialog = await self._send_with_topic_recovery(
                context.tg,
                chat_id=context.target_chat_id,
                telegram_topic_id=dialog.telegram_topic_id,
                bot=context.bot,
                dialog=dialog,
                item_title=context.item_title,
                item_url=context.item_url,
                item_city=context.item_city,
                item_price=context.item_price,
                sender=sender,
                account_name=context.avito_account.name,
                telegram_chat_id=context.telegram_chat_id,
                message_text=notification_text,
            )
            message_id = self._extract_telegram_message_id(send_result)
            if message_id:
                telegram_message_ids.append(message_id)
            telegram_results.append(send_result)
            context.dialog = dialog
            context.telegram_topic_id = dialog.telegram_topic_id

        if not telegram_results:
            logger.info(
                "Avito message %s produced no Telegram deliveries (client=%s dialog=%s)",
                source_message_id,
                client_id,
                avito_dialog_id,
            )

        telegram_topic_id = context.dialog.telegram_topic_id

        await self._update_topic_status(
            context.tg,
            chat_id=context.telegram_chat_id,
            topic_id=telegram_topic_id,
            item_title=context.item_title or f"Диалог {avito_dialog_id}",
            status="incoming",
        )

        attachments_for_storage = attachments_records if attachments_records else None

        display_body = text_value or self._describe_attachments_for_body(attachments_records) or ""

        source_key = source_message_id or (telegram_message_ids[0] if telegram_message_ids else None)

        await self.message_repo.create(
            dialog_id=context.dialog.id,
            direction=MessageDirection.avito.value,
            source_message_id=source_key,
            body=display_body,
            attachments=attachments_for_storage,
            status=MessageStatus.delivered.value,
            telegram_message_id=telegram_message_ids[0] if telegram_message_ids else None,
            is_client_message=True,
        )

        auto_reply_dialog = await self._maybe_send_auto_reply(
            client=client,
            context=context,
            dialog=context.dialog,
            now_utc=datetime.utcnow(),
        )
        if auto_reply_dialog is not None:
            context.dialog = auto_reply_dialog

        return {
            "dialog_id": context.dialog.id,
            "created": context.created,
            "telegram_messages": telegram_results,
        }

    async def handle_avito_order_event(
        self,
        *,
        client_id: int,
        avito_account_id: int,
        avito_dialog_id: str,
        message_text: str,
        source_key: str,
        sender: Optional[str] = None,
        item_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = await self.message_repo.get_by_source(
            direction=MessageDirection.avito.value,
            source_message_id=source_key,
        )
        if existing:
            return {"ignored": True, "reason": "duplicate"}

        client = await self.client_repo.get_by_id(client_id)

        context = await self._ensure_dialog_context(
            client_id=client_id,
            avito_account_id=avito_account_id,
            avito_dialog_id=avito_dialog_id,
            sender=sender,
            item_title=item_title,
            client=client,
        )

        thread_id_int = None
        if context.telegram_topic_id:
            try:
                thread_id_int = int(context.telegram_topic_id)
            except (TypeError, ValueError):
                thread_id_int = None

        telegram_message = await context.tg.send_message(
            chat_id=context.target_chat_id,
            text=message_text,
            message_thread_id=thread_id_int,
        )

        await self.message_repo.create(
            dialog_id=context.dialog.id,
            direction=MessageDirection.avito.value,
            source_message_id=source_key,
            body=message_text,
            status=MessageStatus.delivered.value,
            telegram_message_id=str(telegram_message.get("message_id")) if telegram_message else None,
        )

        await self._update_topic_status(
            context.tg,
            chat_id=context.telegram_chat_id,
            topic_id=context.telegram_topic_id,
            item_title=context.item_title or f"Диалог {avito_dialog_id}",
            status="incoming",
        )

        auto_reply_dialog = await self._maybe_send_auto_reply(
            client=client,
            context=context,
            dialog=context.dialog,
            now_utc=datetime.utcnow(),
        )
        if auto_reply_dialog is not None:
            context.dialog = auto_reply_dialog

        return {"dialog_id": context.dialog.id, "created": context.created, "telegram_message": telegram_message}

    async def _ensure_dialog_context(
        self,
        *,
        client_id: int,
        avito_account_id: int,
        avito_dialog_id: str,
        sender: Optional[str],
        item_title: Optional[str],
        client=None,
    ) -> DialogContext:
        avito_account = await self.avito_repo.get(avito_account_id)
        if avito_account is None or avito_account.client_id != client_id:
            raise ValueError("Avito account not found")
        if avito_account.bot_id is None:
            raise ValueError("Avito account not linked to bot")

        bot = await self.bot_repo.get(avito_account.bot_id)
        if bot is None:
            raise ValueError("Bot not found")

        tg = TelegramService(bot.token)

        bot_updates: Dict[str, Any] = {}
        if bot.status != BotStatus.active:
            bot_updates["status"] = BotStatus.active

        dialog = await self.dialog_repo.get_by_avito(client_id, avito_dialog_id)
        telegram_topic_id = dialog.telegram_topic_id if dialog else None
        telegram_chat_id = dialog.telegram_chat_id if dialog else bot.group_chat_id
        target_chat_id = telegram_chat_id or bot.group_chat_id
        if not target_chat_id:
            raise ValueError("Bot has no target chat configured")

        resolved_item_title, item_url, item_city, item_price = await self._resolve_item_title_and_url(
            avito_account_id=avito_account.id,
            avito_dialog_id=avito_dialog_id,
            current=item_title,
        )

        topic_created = False
        created_flag = False

        if client is None:
            client = await self.client_repo.get_by_id(client_id)

        if dialog is None:
            topic_id = None
            if bot.topic_mode and telegram_chat_id:
                base_title = resolved_item_title or sender or f"Диалог {avito_dialog_id}"
                topic_title = self._compose_topic_title(base_title, status="incoming")
                result = await tg.create_topic(telegram_chat_id, (topic_title or "Диалог")[:128])
                topic_id = (
                    result.get("message_thread_id")
                    or result.get("forum_topic_id")
                    or result.get("topic", {}).get("message_thread_id")
                )
            dialog = await self.dialog_repo.create(
                client_id=client_id,
                bot_id=bot.id,
                avito_dialog_id=avito_dialog_id,
                avito_account_id=avito_account_id,
                source=DialogSource.avito,
                telegram_chat_id=telegram_chat_id,
                telegram_topic_id=str(topic_id) if topic_id else None,
            )
            telegram_topic_id = dialog.telegram_topic_id
            topic_created = bool(telegram_topic_id)
            created_flag = True
        elif bot.topic_mode and telegram_chat_id and not telegram_topic_id:
            base_title = resolved_item_title or sender or f"Диалог {avito_dialog_id}"
            topic_title = self._compose_topic_title(base_title, status="incoming")
            try:
                topic_result = await tg.create_topic(telegram_chat_id, topic_title[:128])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to recreate Telegram topic for %s: %s",
                    avito_dialog_id,
                    exc,
                )
            else:
                topic_id = (
                    topic_result.get("message_thread_id")
                    or topic_result.get("forum_topic_id")
                    or topic_result.get("topic", {}).get("message_thread_id")
                )
                if topic_id:
                    dialog = await self.dialog_repo.set_topic(dialog, str(topic_id))
                    telegram_topic_id = dialog.telegram_topic_id
                    topic_created = True

        dialog_topic_intro_sent = bool(getattr(dialog, "topic_intro_sent", False))

        if (
            (topic_created or not dialog_topic_intro_sent)
            and bot.topic_mode
            and telegram_chat_id
            and telegram_topic_id
        ):
            header_sent = await self._send_topic_header(
                tg,
                chat_id=telegram_chat_id,
                topic_id=telegram_topic_id,
                item_title=resolved_item_title,
                item_url=item_url,
                city_name=item_city,
                item_price=item_price,
                account_name=avito_account.name,
                sender_name=sender,
            )
            if header_sent:
                dialog.topic_intro_sent = True
                await self.session.commit()
                dialog_topic_intro_sent = True
            else:
                logger.warning(
                    "Topic header could not be delivered for dialog %s (topic %s)",
                    dialog.id,
                    telegram_topic_id,
                )

        if not bot.group_chat_id and target_chat_id:
            bot_updates["group_chat_id"] = target_chat_id

        if bot_updates:
            bot = await self.bot_repo.update(bot, **bot_updates)

        await self.dialog_repo.touch(dialog)

        return DialogContext(
            bot=bot,
            dialog=dialog,
            tg=tg,
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            target_chat_id=target_chat_id,
            item_title=resolved_item_title,
            item_url=item_url,
            item_city=item_city,
            item_price=item_price,
            avito_account=avito_account,
            created=created_flag,
            topic_intro_sent=dialog_topic_intro_sent,
        )

    async def _should_ignore_message(
        self,
        *,
        client_id: int,
        message_text: str | None,
        client=None,
    ) -> bool:
        if not message_text:
            return False
        if client is None:
            client = await self.client_repo.get_by_id(client_id)
        if client and getattr(client, "hide_system_messages", True):
            if "[Системное сообщение]" in message_text:
                logger.info("Ignoring Avito message for client %s due to system marker", client_id)
                return True

        filters = self._extract_filter_tokens(client.filter_keywords if client else None)
        if not filters:
            return False
        lowered = message_text.lower()
        return any(token in lowered for token in filters)

    @staticmethod
    def _extract_filter_tokens(filter_keywords: str | None) -> list[str]:
        if not filter_keywords:
            return []
        raw = filter_keywords.replace(',', '\n')
        return [token.strip().lower() for token in raw.splitlines() if token.strip()]

    async def _send_topic_header(
        self,
        tg: TelegramService,
        *,
        chat_id: str,
        topic_id: str,
        item_title: Optional[str],
        item_url: Optional[str] = None,
        city_name: Optional[str] = None,
        item_price: Optional[str] = None,
        account_name: Optional[str],
        sender_name: Optional[str],
    ) -> bool:
        try:
            topic_int = int(topic_id)
        except (TypeError, ValueError):
            logger.warning("Invalid topic id %r for header message", topic_id)
            return False

        raw_item = item_title or "Без названия"
        raw_account = account_name or "Не указан"
        raw_city = city_name or "Не указан"
        raw_sender = sender_name or "Неизвестно"
        raw_price = item_price or "Не указана"

        item_text = escape(raw_item)
        account_text = escape(raw_account)
        city_text = escape(raw_city)
        sender_text = escape(raw_sender)
        price_text = escape(raw_price)

        if item_url:
            item_href = escape(item_url, quote=True)
            item_markup = f"<a href=\"{item_href}\">{item_text}</a>"
        else:
            item_markup = item_text

        header_text = (
            f"<b>Объявление:</b> {item_markup}\n"
            f"💰 Цена: {price_text}\n"
            f"<b>Аккаунт Авито:</b> {account_text}\n"
            f"<b>Город объявления:</b> {city_text}\n"
            f"<b>Клиент:</b> {sender_text}"
        )

        try:
            result = await tg.send_message(
                chat_id=chat_id,
                text=header_text,
                message_thread_id=topic_int if topic_int is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to send topic header in chat %s topic %s: %s",
                chat_id,
                topic_id,
                exc,
            )
            return False

        try:
            await tg.pin_message(
                chat_id=chat_id,
                message_id=result.get("message_id"),
                message_thread_id=topic_int,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to pin header message in chat %s topic %s: %s",
                chat_id,
                topic_id,
                exc,
            )
        return True

    async def _update_topic_status(
        self,
        tg: TelegramService,
        *,
        chat_id: Optional[str],
        topic_id: Optional[str],
        item_title: Optional[str],
        status: str,
    ) -> None:
        if not chat_id or not topic_id:
            return
        try:
            topic_int = int(topic_id)
        except (TypeError, ValueError):
            logger.warning("Invalid topic id %r for status update", topic_id)
            return

        base_title = item_title or f"Диалог {topic_id}"
        title = self._compose_topic_title(base_title, status=status)

        try:
            await tg.edit_topic_name(chat_id, topic_int, title)
        except Exception as exc:  # noqa: BLE001
            detail = ""
            skip = False
            try:
                import httpx

                if isinstance(exc, httpx.HTTPStatusError):
                    detail = exc.response.text
                    if "TOPIC_NOT_MODIFIED" in detail:
                        skip = True
            except Exception:  # noqa: BLE001
                detail = ""
            if skip:
                return
            logger.warning(
                "Failed to edit topic name in chat %s topic %s: %s %s",
                chat_id,
                topic_id,
                exc,
                detail,
            )

    async def _resolve_item_title_and_url(
        self,
        *,
        avito_account_id: int,
        avito_dialog_id: str,
        current: Optional[str],
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        resolved_title = current
        item_url: Optional[str] = None
        city_name: Optional[str] = None
        price_text: Optional[str] = None

        try:
            metadata = await self.avito_service.get_chat_metadata(avito_account_id, avito_dialog_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to fetch Avito chat metadata for %s: %s",
                avito_dialog_id,
                exc,
            )
            return resolved_title, None, None, None

        context = metadata.get("context") or {}
        if context.get("type") != "item":
            return resolved_title, None, None, None

        value = context.get("value") or {}
        raw_title = value.get("title")
        if raw_title:
            resolved_title = raw_title

        url_candidates = [
            value.get("url"),
            value.get("link"),
            value.get("item_url"),
            value.get("itemUrl"),
            value.get("permalink"),
            value.get("shareUrl"),
        ]
        item_url = next((candidate for candidate in url_candidates if isinstance(candidate, str) and candidate.strip()), None)

        if not item_url:
            item_id = value.get("id") or value.get("item_id") or value.get("itemId")
            if item_id:
                item_url = f"https://www.avito.ru/{item_id}"

        if item_url:
            item_url = self._normalize_avito_item_url(item_url)

        location = value.get("location") or value.get("geo") or {}
        if isinstance(location, dict):
            city_name = (
                location.get("title")
                or location.get("city")
                or location.get("cityName")
            )

        price_text = self._extract_price_text(value)
        if not price_text:
            price_text = self._extract_price_text(context)
        if not price_text:
            price_text = self._extract_price_text(metadata)

        return resolved_title, item_url, city_name, price_text

    @staticmethod
    def _normalize_avito_item_url(url: str) -> str:
        candidate = url.strip()
        if not candidate:
            return url
        if candidate.startswith("//"):
            return f"https:{candidate}"
        if candidate.startswith("/"):
            return f"https://www.avito.ru{candidate}"
        if not candidate.startswith(("http://", "https://")):
            return f"https://{candidate}"
        return candidate

    def _extract_price_text(self, payload: Any, *, _depth: int = 0) -> Optional[str]:
        if _depth > 6 or payload is None:
            return None
        if isinstance(payload, dict):
            currency_hint = (
                payload.get("currency")
                or payload.get("currencyCode")
                or payload.get("currency_code")
            )
            for key, value in payload.items():
                if isinstance(key, str) and "price" in key.lower():
                    normalized = self._normalize_price_candidate(value, currency_hint, _depth=_depth + 1)
                    if normalized:
                        return normalized
            for value in payload.values():
                normalized = self._extract_price_text(value, _depth=_depth + 1)
                if normalized:
                    return normalized
            return None
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            for item in payload:
                normalized = self._extract_price_text(item, _depth=_depth + 1)
                if normalized:
                    return normalized
        return None

    def _normalize_price_candidate(
        self,
        candidate: Any,
        currency: Optional[str],
        *,
        _depth: int = 0,
    ) -> Optional[str]:
        if _depth > 6 or candidate is None:
            return None
        if isinstance(candidate, (int, float)):
            return self._format_price_number(candidate, currency)
        if isinstance(candidate, str):
            text = candidate.strip()
            return text or None
        if isinstance(candidate, dict):
            currency_hint = (
                candidate.get("currency")
                or candidate.get("currencyCode")
                or candidate.get("currency_code")
                or currency
            )
            keys_to_try = ("text", "value", "amount", "display", "formatted", "label", "price")
            for key in keys_to_try:
                if key in candidate:
                    normalized = self._normalize_price_candidate(
                        candidate.get(key),
                        currency_hint,
                        _depth=_depth + 1,
                    )
                    if normalized:
                        return normalized
            for key, value in candidate.items():
                if isinstance(key, str) and "price" in key.lower():
                    normalized = self._normalize_price_candidate(value, currency_hint, _depth=_depth + 1)
                    if normalized:
                        return normalized
            for value in candidate.values():
                normalized = self._normalize_price_candidate(value, currency_hint, _depth=_depth + 1)
                if normalized:
                    return normalized
            return None
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
            for item in candidate:
                normalized = self._normalize_price_candidate(item, currency, _depth=_depth + 1)
                if normalized:
                    return normalized
        return None

    @staticmethod
    def _format_price_number(value: float | int, currency: Optional[str]) -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return str(value)
        if abs(amount - round(amount)) < 1e-6:
            formatted_amount = f"{int(round(amount)):,}".replace(",", " ")
        else:
            formatted_amount = f"{amount:,.2f}".replace(",", " ")
            formatted_amount = formatted_amount.rstrip("0").rstrip(",")
        symbol = DialogService._currency_symbol(currency)
        if symbol:
            return f"{formatted_amount} {symbol}".strip()
        if currency:
            return f"{formatted_amount} {currency}".strip()
        return f"{formatted_amount} ₽"

    @staticmethod
    def _currency_symbol(currency: Optional[str]) -> Optional[str]:
        if not currency:
            return None
        normalized = currency.strip().upper()
        mapping = {
            "RUB": "₽",
            "RUR": "₽",
            "RUBLE": "₽",
            "РУБ": "₽",
            "KZT": "₸",
            "BYN": "Br",
            "USD": "$",
            "EUR": "€",
        }
        return mapping.get(normalized, currency if len(normalized) <= 4 else normalized)

    def _compose_topic_title(self, base_title: str, *, status: str) -> str:
        base = base_title or "Диалог"
        emoji_map = {
            "incoming": "🔴",
            "outgoing": "🟢",
            "auto": "🔵",
        }
        prefix = emoji_map.get(status, "🔴")
        title = f"{prefix} Авито - {base}"
        return title[:128]

    def _resolve_avito_image_url(self, attachment: dict[str, Any]) -> str | None:
        candidates = []
        if isinstance(attachment, dict):
            for key in ("url", "image", "payload", "images", "variants", "content"):
                value = attachment.get(key)
                if value is not None:
                    candidates.append(value)

        for candidate in candidates:
            url = self._select_url_from_structure(candidate)
            if url:
                return url

        if isinstance(attachment, dict):
            return self._select_url_from_structure(attachment)
        return None

    def _select_url_from_structure(self, data: Any) -> str | None:
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            priority_keys = ("url", "original", "origin", "src", "value")
            for key in priority_keys:
                value = data.get(key)
                if isinstance(value, str):
                    return value

            sized_candidates: list[tuple[int, str]] = []
            for key, value in data.items():
                if isinstance(value, str):
                    sized_candidates.append((self._parse_size_key(key), value))
                elif isinstance(value, (dict, list, tuple)):
                    nested = self._select_url_from_structure(value)
                    if nested:
                        return nested

            sized_candidates = [item for item in sized_candidates if item[1]]
            if sized_candidates:
                sized_candidates.sort(key=lambda item: item[0], reverse=True)
                return sized_candidates[0][1]

        if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
            for item in data:
                url = self._select_url_from_structure(item)
                if url:
                    return url
        return None

    @staticmethod
    def _parse_size_key(key: str) -> int:
        if not isinstance(key, str):
            return 0
        if "x" in key:
            try:
                width, height = key.lower().split("x", maxsplit=1)
                return int(width) * int(height)
            except (ValueError, TypeError):  # pragma: no cover - defensive
                return 0
        try:
            return int(key)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _extract_telegram_message_id(result: Dict[str, Any] | None) -> Optional[str]:
        if not isinstance(result, dict):
            return None
        message_id_val = result.get("message_id")
        if message_id_val is None:
            message = result.get("message")
            if isinstance(message, dict):
                message_id_val = message.get("message_id")
        if message_id_val is None:
            return None
        try:
            return str(message_id_val)
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _describe_attachments_for_body(attachments: Sequence[dict[str, Any]] | None) -> str | None:
        if not attachments:
            return None
        labels: list[str] = []
        for attachment in attachments:
            label = str(attachment.get("type") or "attachment").strip().lower()
            if label == "image":
                labels.append("[изображение]")
            elif label == "voice":
                labels.append("[голосовое сообщение]")
            else:
                labels.append(f"[{label}]")
        return " ".join(labels) if labels else None

    @staticmethod
    def _extract_telegram_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []

        photos = message.get("photo")
        if isinstance(photos, list):
            def photo_weight(item: dict[str, Any]) -> int:
                return int(item.get("file_size") or 0)

            best_photo = max(photos, key=photo_weight, default=None)
            if isinstance(best_photo, dict):
                attachments.append(
                    {
                        "type": "photo",
                        "file_id": best_photo.get("file_id"),
                        "file_unique_id": best_photo.get("file_unique_id"),
                        "width": best_photo.get("width"),
                        "height": best_photo.get("height"),
                        "file_size": best_photo.get("file_size"),
                    }
                )

        voice = message.get("voice")
        if isinstance(voice, dict):
            attachments.append(
                {
                    "type": "voice",
                    "file_id": voice.get("file_id"),
                    "file_unique_id": voice.get("file_unique_id"),
                    "duration": voice.get("duration"),
                    "mime_type": voice.get("mime_type"),
                }
            )

        document = message.get("document")
        if isinstance(document, dict):
            attachments.append(
                {
                    "type": "document",
                    "file_id": document.get("file_id"),
                    "file_name": document.get("file_name"),
                    "mime_type": document.get("mime_type"),
                }
            )

        return attachments

    async def _send_with_topic_recovery(
        self,
        tg: TelegramService,
        *,
        chat_id: str,
        telegram_topic_id: Optional[str],
        bot: Bot,
        dialog: Dialog,
        item_title: Optional[str],
        item_url: Optional[str],
        item_city: Optional[str],
        item_price: Optional[str],
        sender: Optional[str],
        account_name: Optional[str],
        telegram_chat_id: Optional[str],
        message_text: Optional[str] = None,
        send_func: Callable[[Optional[int]], Awaitable[Dict[str, Any]]] | None = None,
    ) -> tuple[Dict[str, Any], Dialog]:
        if send_func is None:
            if message_text is None:
                raise ValueError("Either message_text or send_func must be provided")

            async def _default_send(thread_id: Optional[int]) -> Dict[str, Any]:
                return await tg.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    message_thread_id=thread_id,
                )

            send_callable = _default_send
        else:
            send_callable = send_func

        thread_id_int = None
        if telegram_topic_id:
            try:
                thread_id_int = int(telegram_topic_id)
            except (TypeError, ValueError):
                logger.warning("Invalid stored topic id %s, resetting", telegram_topic_id)
                dialog = await self.dialog_repo.set_topic(dialog, None)
                telegram_topic_id = None

        try:
            result = await self._execute_with_retry(send_callable, thread_id_int)
            return result, dialog
        except (httpx.HTTPStatusError, ValueError) as exc:
            if not self._is_topic_missing_error(exc):
                raise
            logger.warning(
                "Topic %s missing for dialog %s, recreating",
                telegram_topic_id,
                dialog.avito_dialog_id,
            )
            dialog = await self.dialog_repo.set_topic(dialog, None)
            telegram_topic_id = None

            if not bot.topic_mode or not telegram_chat_id:
                raise

            base_title = item_title or sender or f"Диалог {dialog.avito_dialog_id}"
            topic_title = self._compose_topic_title(base_title, status="incoming")
            topic_result = await tg.create_topic(telegram_chat_id, topic_title[:128])
            topic_id = (
                topic_result.get("message_thread_id")
                or topic_result.get("forum_topic_id")
                or topic_result.get("topic", {}).get("message_thread_id")
            )
            if not topic_id:
                raise ValueError("Failed to create Telegram topic")

            dialog = await self.dialog_repo.set_topic(dialog, str(topic_id))
            telegram_topic_id = dialog.telegram_topic_id

            header_sent = await self._send_topic_header(
                tg,
                chat_id=telegram_chat_id,
                topic_id=telegram_topic_id,
                item_title=item_title,
                item_url=item_url,
                city_name=item_city,
                item_price=item_price,
                account_name=account_name,
                sender_name=sender,
            )

            if header_sent:
                dialog.topic_intro_sent = True
                await self.session.commit()
                await self.session.refresh(dialog)

            try:
                thread_id_int = int(telegram_topic_id)
            except (TypeError, ValueError):
                thread_id_int = None

            result = await self._execute_with_retry(send_callable, thread_id_int)
            return result, dialog

    async def _maybe_send_auto_reply(
        self,
        *,
        client,
        context: DialogContext,
        dialog: Dialog,
        now_utc: datetime,
    ) -> Dialog | None:
        if client is None or not getattr(client, "auto_reply_enabled", False):
            return None

        text_source = getattr(client, "auto_reply_text", None) or ""
        text_value = text_source.strip()
        if not text_value:
            return None

        timezone_name = getattr(client, "auto_reply_timezone", None)
        tzinfo = self._resolve_timezone(timezone_name)
        local_now = now_utc.astimezone(tzinfo)

        auto_reply_always = bool(getattr(client, "auto_reply_always", False))
        start_time: time | None = getattr(client, "auto_reply_start_time", None)
        end_time: time | None = getattr(client, "auto_reply_end_time", None)

        if not auto_reply_always:
            if start_time is None or end_time is None:
                return None
            if not self._is_time_within_window(local_now.time(), start_time, end_time):
                return None

        window_start_local = self._calculate_window_start(
            local_now=local_now,
            auto_reply_always=auto_reply_always,
            start_time=start_time,
            end_time=end_time,
        )

        if dialog.auto_reply_last_sent_at is not None and window_start_local is not None:
            last_local = dialog.auto_reply_last_sent_at.astimezone(tzinfo)
            if last_local >= window_start_local:
                return None

        window_start_local = self._calculate_window_start(
            local_now=local_now,
            auto_reply_always=auto_reply_always,
            start_time=start_time,
            end_time=end_time,
        )

        if window_start_local is not None and dialog.auto_reply_last_sent_at is not None:
            last_local = dialog.auto_reply_last_sent_at.astimezone(tzinfo)
            if last_local >= window_start_local:
                return None

        scheduled_at = datetime.utcnow()
        dialog = await self.dialog_repo.set_auto_reply_schedule(dialog, scheduled_at)
        self._schedule_auto_reply(dialog_id=dialog.id, scheduled_at=scheduled_at)
        logger.info(
            "Auto-reply scheduled for dialog %s in %s seconds",
            dialog.avito_dialog_id,
            AUTO_REPLY_DELAY_SECONDS,
        )
        return None

    def _schedule_auto_reply(
        self,
        *,
        dialog_id: int,
        scheduled_at: datetime,
        delay_seconds: int = AUTO_REPLY_DELAY_SECONDS,
    ) -> None:
        async def runner() -> None:
            try:
                await asyncio.sleep(delay_seconds)
                async with SessionLocal() as session:
                    service = DialogService(session)
                    await service._execute_scheduled_auto_reply(dialog_id=dialog_id, scheduled_at=scheduled_at)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to execute scheduled auto-reply", extra={"dialog_id": dialog_id})

        asyncio.create_task(runner())

    async def _execute_scheduled_auto_reply(self, *, dialog_id: int, scheduled_at: datetime) -> None:
        dialog = await self.dialog_repo.get(dialog_id)
        if dialog is None:
            return

        stored_schedule = getattr(dialog, "auto_reply_scheduled_at", None)
        if stored_schedule is None or stored_schedule != scheduled_at:
            return

        client = await self.client_repo.get_by_id(dialog.client_id)
        if client is None or not getattr(client, "auto_reply_enabled", False):
            await self.dialog_repo.clear_auto_reply_schedule(dialog)
            return

        text_source = getattr(client, "auto_reply_text", None) or ""
        text_value = text_source.strip()
        if not text_value:
            await self.dialog_repo.clear_auto_reply_schedule(dialog)
            return

        if await self.message_repo.has_outgoing_since(dialog.id, scheduled_at):
            await self.dialog_repo.clear_auto_reply_schedule(dialog)
            return

        tzinfo = self._resolve_timezone(getattr(client, "auto_reply_timezone", None))
        local_now = datetime.now(tzinfo)

        auto_reply_always = bool(getattr(client, "auto_reply_always", False))
        start_time: time | None = getattr(client, "auto_reply_start_time", None)
        end_time: time | None = getattr(client, "auto_reply_end_time", None)

        if not auto_reply_always:
            if start_time is None or end_time is None:
                await self.dialog_repo.clear_auto_reply_schedule(dialog)
                return
            if not self._is_time_within_window(local_now.time(), start_time, end_time):
                await self.dialog_repo.clear_auto_reply_schedule(dialog)
                return

        window_start_local = self._calculate_window_start(
            local_now=local_now,
            auto_reply_always=auto_reply_always,
            start_time=start_time,
            end_time=end_time,
        )
        if window_start_local is not None and dialog.auto_reply_last_sent_at is not None:
            last_local = dialog.auto_reply_last_sent_at.astimezone(tzinfo)
            if last_local >= window_start_local:
                await self.dialog_repo.clear_auto_reply_schedule(dialog)
                return

        context = await self._ensure_dialog_context(
            client_id=dialog.client_id,
            avito_account_id=dialog.avito_account_id,
            avito_dialog_id=dialog.avito_dialog_id,
            sender=None,
            item_title=None,
            client=client,
        )

        telegram_text = f"🤖 Автоответчик: {text_value}"
        dialog = await self._send_auto_reply_message(
            context=context,
            dialog=context.dialog,
            telegram_text=telegram_text,
            avito_text=text_value,
        )

        await self.dialog_repo.mark_auto_reply_sent(dialog, datetime.utcnow())
        logger.info(
            "Auto-reply sent for dialog %s (client=%s)",
            dialog.avito_dialog_id,
            dialog.client_id,
        )

    async def _send_auto_reply_message(
        self,
        *,
        context: DialogContext,
        dialog: Dialog,
        telegram_text: str,
        avito_text: str,
    ) -> Dialog:
        send_result, dialog = await self._send_with_topic_recovery(
            context.tg,
            chat_id=context.target_chat_id,
            telegram_topic_id=dialog.telegram_topic_id,
            bot=context.bot,
            dialog=dialog,
            item_title=context.item_title,
            item_url=context.item_url,
            item_city=context.item_city,
            item_price=context.item_price,
            sender=None,
            account_name=context.avito_account.name,
            telegram_chat_id=context.telegram_chat_id,
            message_text=telegram_text,
        )

        message_id = self._extract_telegram_message_id(send_result)

        outgoing_message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.telegram.value,
            source_message_id=message_id,
            body=telegram_text,
            status=MessageStatus.sent.value,
            telegram_message_id=message_id,
            is_auto_reply=True,
        )

        dialog = await self.dialog_repo.touch(dialog)

        await TaskQueue.enqueue(
            "avito.send_message",
            {
                "account_id": dialog.avito_account_id,
                "dialog_id": dialog.avito_dialog_id,
                "kind": "text",
                "text": avito_text,
                "message_db_id": outgoing_message.id,
                "bot_token": getattr(context.bot, "token", None),
                "telegram_chat_id": context.target_chat_id,
                "telegram_topic_id": dialog.telegram_topic_id,
                "status_on_success": "auto",
                "topic_item_title": context.item_title,
            },
        )

        await self._update_topic_status(
            context.tg,
            chat_id=context.telegram_chat_id,
            topic_id=dialog.telegram_topic_id,
            item_title=context.item_title or f"Диалог {dialog.avito_dialog_id}",
            status="auto",
        )

        return dialog

    @staticmethod
    def _is_time_within_window(current: time, start: time, end: time) -> bool:
        if start == end:
            return False
        if start < end:
            return start <= current < end
        return current >= start or current < end

    @staticmethod
    def _resolve_timezone(tz_name: str | None) -> ZoneInfo:
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                logger.warning("Unknown timezone %s, falling back to UTC", tz_name)
        return ZoneInfo("UTC")

    @staticmethod
    def _calculate_window_start(
        *,
        local_now: datetime,
        auto_reply_always: bool,
        start_time: time | None,
        end_time: time | None,
    ) -> datetime | None:
        tzinfo = local_now.tzinfo
        if tzinfo is None:
            return None

        if auto_reply_always:
            return datetime.combine(local_now.date(), time.min, tzinfo=tzinfo)

        if start_time is None or end_time is None:
            return None

        if start_time <= end_time:
            start_today = datetime.combine(local_now.date(), start_time, tzinfo=tzinfo)
            if local_now >= start_today:
                return start_today
            prev_date = local_now.date() - timedelta(days=1)
            return datetime.combine(prev_date, start_time, tzinfo=tzinfo)

        # overnight window (start > end)
        start_today = datetime.combine(local_now.date(), start_time, tzinfo=tzinfo)
        if local_now.time() >= start_time:
            return start_today
        prev_date = local_now.date() - timedelta(days=1)
        return datetime.combine(prev_date, start_time, tzinfo=tzinfo)

    @staticmethod
    def _is_topic_missing_error(exc: Exception) -> bool:
        message = ""
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                payload = exc.response.json()
                message = str(payload.get("description") or payload)
            except Exception:  # noqa: BLE001
                message = exc.response.text
        elif isinstance(exc, ValueError) and exc.args:
            payload = exc.args[0]
            if isinstance(payload, dict):
                message = str(payload.get("description") or payload)
            else:
                message = str(payload)
        else:
            message = str(exc)

        message = message.lower()
        return any(
            phrase in message
            for phrase in (
                "message thread not found",
                "message_thread_not_found",
                "invalid message thread id",
                "message can't be sent to thread",
                "thread not found",
            )
        )

    async def _execute_with_retry(
        self,
        send_callable: Callable[[Optional[int]], Awaitable[Dict[str, Any]]],
        thread_id: Optional[int],
        *,
        retries: int = 1,
        delay_seconds: float = 1.0,
    ) -> Dict[str, Any]:
        attempt = 0
        while True:
            try:
                return await send_callable(thread_id)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response else None
                if status_code == 429 and attempt < retries:
                    wait_time = max(delay_seconds, float(exc.response.headers.get("Retry-After", delay_seconds))) if exc.response else delay_seconds
                    logger.warning(
                        "Telegram rate limit (429) encountered, retrying after %.1fs",
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    attempt += 1
                    continue
                raise

    async def _download_media(self, url: str) -> tuple[bytes, str | None, str | None]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type")
            disposition = response.headers.get("content-disposition")

        filename = None
        if disposition and "filename=" in disposition:
            filename = disposition.split("filename=")[-1].strip('"')

        return content, filename, content_type

    async def handle_telegram_message(
        self,
        *,
        bot_token: str,
        chat_id: str,
        telegram_message: dict[str, Any],
        message_id: Optional[str],
        message_thread_id: Optional[str],
        reply_to_message_id: Optional[str],
    ) -> Dict[str, Any]:
        bot = await self.bot_repo.get_by_token(bot_token)
        if bot is None:
            raise ValueError("Bot not registered")
        bot_updates: Dict[str, Any] = {}
        if bot.status != BotStatus.active:
            bot_updates["status"] = BotStatus.active
        if not bot.group_chat_id and chat_id:
            bot_updates["group_chat_id"] = chat_id
        if bot_updates:
            bot = await self.bot_repo.update(bot, **bot_updates)
        tg = TelegramService(bot.token)
        source_message = None
        if reply_to_message_id:
            source_message = await self.message_repo.get_by_source(
                direction=MessageDirection.avito.value,
                source_message_id=reply_to_message_id,
            )
            if source_message is None:
                source_message = await self.message_repo.get_by_telegram(
                    telegram_message_id=reply_to_message_id,
                    direction=MessageDirection.avito.value,
                )
            if source_message is None:
                source_message = await self.message_repo.get_by_telegram(
                    telegram_message_id=reply_to_message_id,
                )
        logger.info(
            "Telegram reply context",
            reply_to=reply_to_message_id,
            source_found=bool(source_message),
            bot_id=bot.id,
        )

        text = telegram_message.get("text") or telegram_message.get("caption") or ""
        attachments = self._extract_telegram_attachments(telegram_message)

        if not text and not attachments:
            raise ValueError("Empty Telegram payload")

        dialog = None
        if message_thread_id:
            dialog = await self.dialog_repo.get_by_topic(bot.id, message_thread_id)
        if dialog is None and source_message is not None:
            dialog = await self.dialog_repo.get(source_message.dialog_id)
            if dialog and message_thread_id is None and dialog.telegram_topic_id:
                message_thread_id = dialog.telegram_topic_id
        if dialog is None and message_thread_id is None:
            dialog = await self.dialog_repo.get_recent_by_chat(bot.id, chat_id)
            if dialog and dialog.telegram_topic_id and dialog.telegram_topic_id != message_thread_id:
                # align implicit topic for downstream logging/diagnostics
                message_thread_id = dialog.telegram_topic_id

        if dialog is None:
            raise ValueError("Dialog not found for message")

        if message_thread_id and (dialog.telegram_topic_id is None or dialog.telegram_topic_id != message_thread_id):
            thread_id_str = str(message_thread_id)
            dialog = await self.dialog_repo.set_topic(dialog, thread_id_str)
            telegram_topic_id = thread_id_str
        else:
            telegram_topic_id = dialog.telegram_topic_id

        if dialog.source == DialogSource.telegram.value:
            from app.services.telegram_source import TelegramSourceService

            telegram_source_service = TelegramSourceService(self.session)
            return await telegram_source_service.handle_manager_reply(
                dialog=dialog,
                bot=bot,
                telegram_message=telegram_message,
                message_id=message_id,
            )

        client = await self.client_repo.get_by_id(dialog.client_id)
        require_reply = bool(getattr(client, "require_reply_for_avito", False)) if client else False

        reply_payload = telegram_message.get("reply_to_message") if isinstance(telegram_message.get("reply_to_message"), dict) else None
        reply_text = ""
        if reply_payload:
            reply_text = reply_payload.get("text") or reply_payload.get("caption") or ""
        has_client_marker = bool(reply_text and "💬 Клиент" in reply_text)

        quoted_client_message = bool(
            source_message
            and (
                source_message.is_client_message
                or source_message.direction == MessageDirection.avito.value
            )
        )

        if quoted_client_message and has_client_marker and source_message and not source_message.is_client_message:
            source_message = await self.message_repo.mark_as_client_message(source_message)

        should_enqueue = not require_reply or (quoted_client_message and has_client_marker)

        attachment_records: list[dict[str, Any]] = attachments if attachments else []
        for attachment in attachment_records:
            attachment.setdefault("queued", False)

        body_value = text or self._describe_attachments_for_body(attachment_records) or ""

        outgoing_message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.telegram.value,
            source_message_id=message_id,
            body=body_value,
            attachments=attachment_records if attachment_records else None,
            status=MessageStatus.sent.value if should_enqueue else MessageStatus.pending.value,
            telegram_message_id=message_id,
        )
        await self.dialog_repo.touch(dialog)

        if not outgoing_message.is_auto_reply:
            dialog = await self.dialog_repo.clear_auto_reply_schedule(dialog)

        item_title, _, _, _ = await self._resolve_item_title_and_url(
            avito_account_id=dialog.avito_account_id,
            avito_dialog_id=dialog.avito_dialog_id,
            current=None,
        )

        enqueue_results: list[dict[str, Any]] = []
        status_should_update = False

        if should_enqueue and text and dialog.source != DialogSource.telegram.value:
            await TaskQueue.enqueue(
                "avito.send_message",
                {
                    "account_id": dialog.avito_account_id,
                    "dialog_id": dialog.avito_dialog_id,
                    "kind": "text",
                    "text": text,
                    "message_db_id": outgoing_message.id,
                    "bot_token": bot.token,
                    "telegram_chat_id": chat_id,
                    "telegram_topic_id": telegram_topic_id,
                    "status_on_success": "outgoing",
                    "topic_item_title": item_title,
                },
            )
            enqueue_results.append({"kind": "text"})
            status_should_update = True
        elif text:
            logger.info(
                "Skipped sending Telegram text message %s to Avito (client=%s) because reply requirement not met",
                outgoing_message.id,
                dialog.client_id,
            )

        if should_enqueue and attachment_records and dialog.source != DialogSource.telegram.value:
            for attachment in attachment_records:
                kind = attachment.get("type")
                if kind == "photo":
                    await TaskQueue.enqueue(
                        "avito.send_message",
                        {
                            "account_id": dialog.avito_account_id,
                            "dialog_id": dialog.avito_dialog_id,
                            "kind": "image",
                            "file_id": attachment.get("file_id"),
                            "file_unique_id": attachment.get("file_unique_id"),
                            "message_db_id": outgoing_message.id,
                            "bot_token": bot.token,
                            "telegram_chat_id": chat_id,
                            "telegram_topic_id": telegram_topic_id,
                            "status_on_success": "outgoing",
                            "topic_item_title": item_title,
                        },
                    )
                    enqueue_results.append({"kind": "image", "file_id": attachment.get("file_id")})
                    attachment["queued"] = True
                    status_should_update = True
                else:
                    logger.info(
                        "Attachment kind %s is not supported for Avito outbound messages", kind,
                    )
        elif attachments and not should_enqueue:
            logger.info(
                "Skipped sending attachments for message %s due to reply requirement",
                outgoing_message.id,
            )

        if status_should_update:
            await self._update_topic_status(
                tg,
                chat_id=chat_id,
                topic_id=dialog.telegram_topic_id or telegram_topic_id,
                item_title=item_title or f"Диалог {dialog.avito_dialog_id}",
                status="outgoing",
            )

        return {
            "dialog_id": dialog.id,
            "queued": should_enqueue,
            "tasks": enqueue_results,
        }

    async def send_portal_text_message(self, *, dialog: Dialog, text: str) -> dict[str, Any]:
        text_value = text.strip()
        if not text_value:
            raise ValueError("Текст сообщения не может быть пустым")

        bot = await self.bot_repo.get(dialog.bot_id)
        if bot is None:
            raise ValueError("Bot not found")

        target_chat_id = dialog.telegram_chat_id or bot.group_chat_id
        if not target_chat_id:
            raise ValueError("Для диалога не настроен чат Telegram")

        client = await self.client_repo.get_by_id(dialog.client_id)
        require_reply = bool(getattr(client, "require_reply_for_avito", False)) if client else False
        if require_reply:
            raise ValueError("Для отправки сообщений требуется отвечать в Telegram с цитированием")

        thread_id = None
        if dialog.telegram_topic_id:
            try:
                thread_id = int(dialog.telegram_topic_id)
            except (TypeError, ValueError):
                thread_id = None

        tg = TelegramService(bot.token)
        try:
            send_result = await tg.send_message(
                chat_id=target_chat_id,
                text=text_value,
                message_thread_id=thread_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Не удалось отправить сообщение в Telegram") from exc

        message_id_value = send_result.get("message_id")
        try:
            message_id = str(message_id_value)
        except Exception:  # pragma: no cover - defensive
            message_id = str(message_id_value) if message_id_value is not None else None

        if not message_id:
            raise ValueError("Telegram не вернул идентификатор сообщения")

        outgoing_message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.telegram.value,
            source_message_id=message_id,
            body=text_value,
            status=MessageStatus.sent.value,
            telegram_message_id=message_id,
        )

        await self.dialog_repo.touch(dialog)

        item_title, _, _, _ = await self._resolve_item_title_and_url(
            avito_account_id=dialog.avito_account_id,
            avito_dialog_id=dialog.avito_dialog_id,
            current=None,
        )

        await TaskQueue.enqueue(
            "avito.send_message",
            {
                "account_id": dialog.avito_account_id,
                "dialog_id": dialog.avito_dialog_id,
                "kind": "text",
                "text": text_value,
                "message_db_id": outgoing_message.id,
                "bot_token": bot.token,
                "telegram_chat_id": target_chat_id,
                "telegram_topic_id": dialog.telegram_topic_id,
                "status_on_success": "outgoing",
                "topic_item_title": item_title,
            },
        )

        await self._update_topic_status(
            tg,
            chat_id=target_chat_id,
            topic_id=dialog.telegram_topic_id,
            item_title=item_title or f"Диалог {dialog.avito_dialog_id}",
            status="outgoing",
        )

        return {
            "status": "sent",
            "telegram_message_id": message_id,
            "telegram_chat_id": target_chat_id,
            "telegram_topic_id": dialog.telegram_topic_id,
        }
