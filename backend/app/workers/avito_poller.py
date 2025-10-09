from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from html import escape
from typing import Any, Iterable, Tuple
from urllib.parse import quote

import httpx
import redis.asyncio as redis
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.avito import AvitoAccount
from app.models.enums import AvitoAccountStatus
from app.services.avito import AvitoService
from app.services.dialog import DialogService
from app.services.queue import TaskQueue

LOGGER = logging.getLogger("tuberry.avito_poller")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

DEFAULT_TIMEOUT = 60.0
DEFAULT_CONNECT_TIMEOUT = 30.0
ORDER_STATUSES_NEW = ["on_confirmation"]
CHAT_MESSAGES_LIMIT = 50


def extract_message(chat: dict[str, Any]) -> Tuple[str | None, str | None, str | None]:
    """Вернуть текст последнего сообщения, имя отправителя и название объявления."""
    last_message = chat.get("last_message") or {}
    text: str | None = None

    content = last_message.get("content") or {}
    if isinstance(content, dict):
        text = content.get("text") or content.get("value")

    if not text and isinstance(last_message.get("parts"), list):
        for part in last_message["parts"]:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text") or part.get("content")
                if text:
                    break

    if not text:
        text = last_message.get("text")

    sender = None
    for user in chat.get("users", []) or []:
        if not user.get("is_self"):
            sender = user.get("name") or sender
            break

    item_title = None
    context = chat.get("context") or {}
    if context.get("type") == "item":
        value = context.get("value") or {}
        item_title = value.get("title")

    return text, sender, item_title


async def fetch_unread(token: str, user_id: str) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{settings.avito_api_base}/messenger/v2/accounts/{user_id}/chats",
            params={"unread_only": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    return payload.get("chats") or []


async def fetch_chat_messages(token: str, user_id: str, chat_id: str) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    encoded_chat_id = quote(str(chat_id), safe="")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{settings.avito_api_base}/messenger/v3/accounts/{user_id}/chats/{encoded_chat_id}/messages",
            params={"unread_only": "true", "limit": str(CHAT_MESSAGES_LIMIT)},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    return payload.get("messages") or []


def extract_author_id(author: dict[str, Any]) -> str | None:
    """Вернуть строковый идентификатор автора, если он присутствует."""
    if not isinstance(author, dict):
        return None
    for key in ("id", "user_id", "userId", "userID"):
        value = author.get(key)
        if value is None:
            continue
        return str(value)
    return None


def collect_self_user_ids(chat: dict[str, Any], fallback_user_id: str | None) -> set[str]:
    """Собрать список идентификаторов, принадлежащих нашему менеджеру."""
    result: set[str] = set()
    if fallback_user_id:
        result.add(str(fallback_user_id))

    users = chat.get("users") or []
    if isinstance(users, Iterable):
        for user in users:
            if not isinstance(user, dict):
                continue
            candidate = extract_author_id(user)
            if candidate is None and isinstance(user.get("user"), dict):
                candidate = extract_author_id(user.get("user"))
            if candidate is None:
                continue
            if user.get("is_self") or (fallback_user_id and str(candidate) == str(fallback_user_id)):
                result.add(str(candidate))

    return result


def extract_message_text(message: dict[str, Any]) -> str | None:
    container = message.get("message") if isinstance(message.get("message"), dict) else message
    text = container.get("text") if isinstance(container, dict) else None
    if text:
        return text
    content = container.get("content") or {}
    if isinstance(content, dict):
        text = content.get("text") or content.get("value")
        if text:
            return text
    parts = container.get("parts")
    if isinstance(parts, Iterable):
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text") or part.get("content")
                if text:
                    return text
    return None


def extract_message_attachments(message: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    container = message.get("message") if isinstance(message.get("message"), dict) else message
    msg_type = container.get("type") or message.get("type")
    content = container.get("content") if isinstance(container, dict) else {}
    attachments: list[dict[str, Any]] = []
    seen_images: set[str] = set()
    seen_voices: set[str] = set()

    def add_image_payload(payload: Any) -> None:
        key = repr(payload)
        if key in seen_images:
            return
        seen_images.add(key)
        attachments.append({"type": "image", "payload": payload})

    def add_voice_payload(voice_id: str, payload: Any) -> None:
        if voice_id in seen_voices:
            return
        seen_voices.add(voice_id)
        attachments.append({"type": "voice", "voice_id": voice_id, "payload": payload})

    if isinstance(content, dict):
        image_payload = content.get("image")
        if image_payload:
            add_image_payload(image_payload)

        images_payload = content.get("images")
        if images_payload:
            add_image_payload(images_payload)

        attachments_list = content.get("attachments")
        if isinstance(attachments_list, Iterable):
            for item in attachments_list:
                if not isinstance(item, dict):
                    continue
                part_type = str(item.get("type") or "").lower()
                if part_type == "image":
                    add_image_payload(item.get("image") or item)
                elif part_type == "voice":
                    voice_id = item.get("voice_id") or item.get("id")
                    if voice_id:
                        add_voice_payload(str(voice_id), item)

        voice_payload = content.get("voice")
        voice_id = None
        if isinstance(voice_payload, dict):
            voice_id = voice_payload.get("voice_id") or voice_payload.get("id")
        if not voice_id and "voice_id" in content:
            voice_id = content.get("voice_id")
        if voice_id:
            add_voice_payload(str(voice_id), voice_payload or content)

    container_voice_id = None
    if isinstance(container, dict):
        container_voice_id = container.get("voice_id") or container.get("voiceId")
    if container_voice_id:
        add_voice_payload(str(container_voice_id), container)

    parts = container.get("parts") if isinstance(container, dict) else None
    if isinstance(parts, Iterable):
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "").lower()
            if part_type == "image":
                add_image_payload(part.get("image") or part)
            elif part_type == "voice":
                voice_id = part.get("voice_id") or part.get("id")
                if voice_id:
                    add_voice_payload(str(voice_id), part)

    return (str(msg_type).lower() if msg_type else None, attachments)


async def mark_chat_read(token: str, user_id: str, chat_id: str) -> None:
    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    encoded_chat_id = quote(str(chat_id), safe="")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.avito_api_base}/messenger/v1/accounts/{user_id}/chats/{encoded_chat_id}/read",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()


async def process_chat(
    *,
    chat: dict[str, Any],
    account_id: int,
    client_id: int,
    token: str,
    user_id: str,
    mark_read: bool,
) -> None:
    LOGGER.info("raw chat payload: %s", chat)
    chat_id = str(chat.get("id"))
    text, sender, item_title = extract_message(chat)

    self_user_ids = collect_self_user_ids(chat, user_id)
    user_name_map: dict[str, str] = {}
    for participant in chat.get("users", []) or []:
        if not isinstance(participant, dict):
            continue
        participant_id = participant.get("id")
        if participant_id is None:
            continue
        user_name_map[str(participant_id)] = participant.get("name") or user_name_map.get(str(participant_id), "")

    messages = []
    try:
        messages = await fetch_chat_messages(token, user_id, chat_id)
    except Exception:
        LOGGER.exception("account %s chat %s: failed to fetch messages", account_id, chat_id)

    if not messages:
        LOGGER.debug("chat %s: no unread messages returned by API", chat_id)
        return

    LOGGER.debug(
        "account %s chat %s: fetched %d unread messages",
        account_id,
        chat_id,
        len(messages),
    )

    messages = list(reversed(messages))

    async with SessionLocal() as session:
        dialog_service = DialogService(session)
        for msg in messages:
            container = msg.get("message") if isinstance(msg.get("message"), dict) else {}
            message_id_raw = msg.get("id") or container.get("id")
            message_id = str(message_id_raw) if message_id_raw is not None else None
            if message_id:
                cached = await TaskQueue.pop_outbound_message(message_id)
                if cached is not None:
                    LOGGER.info(
                        "chat %s: skip message %s as outbound echo (cached=%s)",
                        chat_id,
                        message_id,
                        cached,
                    )
                    continue
            msg_type, msg_attachments = extract_message_attachments(msg)
            msg_text = extract_message_text(msg)
            if not msg_text and not msg_attachments:
                LOGGER.debug(
                    "chat %s: skip message %s without text or attachments",
                    chat_id,
                    message_id,
                )
                continue

            author = msg.get("author") or container.get("author") or {}
            author_id_value = (
                msg.get("author_id")
                or container.get("author_id")
                or author.get("id")
            )
            author_id = str(author_id_value) if author_id_value is not None else None
            direction = (
                msg.get("direction")
                or container.get("direction")
                or (
                    container.get("message") if isinstance(container.get("message"), dict) else {}
                ).get("direction")
            )
            if isinstance(direction, str) and direction.lower() in {
                "outgoing",
                "outbound",
                "out",
                "seller",
                "seller_to_buyer",
                "self",
                "sent",
            }:
                LOGGER.debug(
                    "chat %s: skip message %s due to direction=%s",
                    chat_id,
                    message_id,
                    direction,
                )
                continue

            if author.get("is_self") or (author_id and author_id in self_user_ids):
                LOGGER.debug(
                    "chat %s: skip message %s from self author %s",
                    chat_id,
                    message_id,
                    author_id,
                )
                continue

            sender_name = author.get("name") or user_name_map.get(author_id, sender)
            LOGGER.debug(
                "chat %s: processing message %s (text_len=%d attachments=%d type=%s)",
                chat_id,
                message_id,
                len(msg_text or ""),
                len(msg_attachments),
                msg_type,
            )
            if msg_attachments:
                LOGGER.debug(
                    "chat %s: message %s attachments payload=%s",
                    chat_id,
                    message_id,
                    msg_attachments,
                )
            try:
                dialog_service_result = await dialog_service.handle_avito_message(
                    client_id=client_id,
                    avito_account_id=account_id,
                    avito_dialog_id=chat_id,
                    message_text=msg_text,
                    sender=sender_name,
                    item_title=item_title,
                    source_message_id=message_id,
                    attachments=msg_attachments,
                    message_type=msg_type,
                )
                LOGGER.debug(
                    "chat %s message %s handled: %s",
                    chat_id,
                    message_id,
                    dialog_service_result,
                )
            except Exception:
                LOGGER.exception("chat %s: failed to handle message %s", chat_id, message_id)

    if mark_read:
        await mark_chat_read(token, user_id, chat_id)
        LOGGER.info("marked chat %s as read", chat_id)


async def process_account(account: AvitoAccount, mark_read: bool) -> None:
    service = AvitoService()
    async with service._account_context(account.id) as (account_ctx, repo):
        token = await service._ensure_access_token(account_ctx, repo)
        user_id = await service._get_account_user_id(account_ctx.id, token)
        LOGGER.info("account %s (%s) user_id %s", account_ctx.id, account_ctx.client_id, user_id)

    try:
        await process_orders_for_account(account, service)
    except Exception:
        LOGGER.exception("account %s: failed to process orders", account.id)

    chats = await fetch_unread(token, user_id)
    if not chats:
        LOGGER.debug("account %s: no unread chats", account.id)
        return

    for chat in chats:
        try:
            await process_chat(
                chat=chat,
                account_id=account.id,
                client_id=account.client_id,
                token=token,
                user_id=user_id,
                mark_read=mark_read,
            )
        except Exception:
            LOGGER.exception("account %s: failed to process chat %s", account.id, chat.get("id"))


async def poll_once(mark_read: bool) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AvitoAccount).where(
                AvitoAccount.status == AvitoAccountStatus.active,
                AvitoAccount.bot_id.is_not(None),
                AvitoAccount.monitoring_enabled.is_(True),
            )
        )
        accounts = list(result.scalars().all())

    if not accounts:
        LOGGER.debug("no linked Avito accounts to poll")
        return

    for account in accounts:
        try:
            await process_account(account, mark_read)
        except Exception:
            LOGGER.exception("failed to poll account %s", account.id)


def _parse_iso_timestamp(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _build_order_message(order: dict[str, Any], item: dict[str, Any]) -> str:
    lines: list[str] = ["🛒 <b>Оформлена покупка</b>"]

    order_id = order.get("id")
    if order_id:
        lines.append(f"<b>Заказ:</b> {escape(str(order_id))}")

    title = item.get("title")
    if title:
        lines.append(f"<b>Товар:</b> {escape(str(title))}")

    count = item.get("count")
    if count:
        lines.append(f"<b>Количество:</b> {count}")

    price = order.get("prices", {}).get("price")
    if price is not None:
        lines.append(f"<b>Сумма заказа:</b> {price} ₽")

    buyer_name = (
        order.get("delivery", {})
        .get("buyerInfo", {})
        .get("fullName")
    )
    if buyer_name:
        lines.append(f"<b>Покупатель:</b> {escape(str(buyer_name))}")

    service_type = order.get("delivery", {}).get("serviceType")
    if service_type:
        lines.append(f"<b>Доставка:</b> {escape(str(service_type))}")

    created_at = order.get("createdAt")
    if created_at:
        lines.append(f"<b>Создан:</b> {escape(str(created_at))}")

    lines.append("\n<em>Сообщение создано автоматически</em>")
    return "\n".join(lines)


async def process_orders_for_account(account: AvitoAccount, service: AvitoService) -> None:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_key = f"tuberry:orders:last_ts:{account.id}"

    last_ts_raw = await redis_client.get(redis_key)
    last_ts = int(last_ts_raw) if last_ts_raw else None

    if last_ts is None:
        last_ts = int(datetime.now(timezone.utc).timestamp()) - 86400

    orders = await service.list_orders(
        account.id,
        statuses=ORDER_STATUSES_NEW,
        date_from=last_ts,
    )

    if not orders:
        return

    max_ts = last_ts or 0

    async with SessionLocal() as session:
        dialog_service = DialogService(session)
        for order in orders:
            order_ts = _parse_iso_timestamp(order.get("createdAt"))
            if order_ts and order_ts > max_ts:
                max_ts = order_ts

            items = order.get("items") or []
            for item in items:
                chat_id = item.get("chatId")
                if not chat_id:
                    continue

                message_text = _build_order_message(order, item)
                buyer_name = (
                    order.get("delivery", {})
                    .get("buyerInfo", {})
                    .get("fullName")
                )
                source_key = f"order:{order.get('id')}:created"

                try:
                    await dialog_service.handle_avito_order_event(
                        client_id=account.client_id,
                        avito_account_id=account.id,
                        avito_dialog_id=str(chat_id),
                        message_text=message_text,
                        source_key=source_key,
                        sender=buyer_name,
                        item_title=item.get("title"),
                    )
                except Exception:
                    LOGGER.exception(
                        "account %s: failed to notify about order %s",
                        account.id,
                        order.get("id"),
                    )

    if max_ts:
        await redis_client.set(redis_key, str(max_ts))
    await redis_client.aclose()


async def run_poller(*, once: bool) -> None:
    interval = max(5, settings.avito_poller_interval)
    mark_read = settings.avito_poller_mark_read
    LOGGER.info("Avito poller started (interval=%ss, mark_read=%s)", interval, mark_read)

    while True:
        try:
            await poll_once(mark_read)
        except Exception:
            LOGGER.exception("poll iteration failed")
        if once:
            break
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tuberry Avito poller")
    parser.add_argument("--once", action="store_true", help="Выполнить один проход и завершиться")
    args = parser.parse_args()
    asyncio.run(run_poller(once=args.once))
