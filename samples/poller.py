"""Одноразовый поллер Avito Messenger API.

Сценарий запускается внутри backend-контейнера и доставляет непрочитанные сообщения
в Telegram через `DialogService.handle_avito_message`. После успешной обработки
чаты помечаются прочитанными.

Пример запуска (берёт значения из env):
    docker compose exec -T backend python samples/poller.py \
        --account-id 5 \
        --client-id 1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any

import httpx

from app.db.session import SessionLocal
from app.services.avito import AvitoService
from app.services.dialog import DialogService

LOGGER = logging.getLogger("tuberry.poller")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

DEFAULT_TIMEOUT = 60.0
DEFAULT_CONNECT_TIMEOUT = 30.0


def extract_message(chat: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Возвращает текст последнего сообщения, имя отправителя и название объявления."""
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


async def mark_chat_read(token: str, user_id: str, chat_id: str) -> None:
    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/read",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()


async def fetch_unread(token: str, user_id: str) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats",
            params={"unread_only": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    return payload.get("chats") or []


async def process_chat(
    chat: dict[str, Any],
    client_id: int,
    account_id: int,
    token: str,
    user_id: str,
    mark_read: bool,
) -> None:
    chat_id = str(chat.get("id"))
    text, sender, item_title = extract_message(chat)

    if not text:
        LOGGER.info("skip chat %s: no text payload", chat_id)
        if mark_read:
            await mark_chat_read(token, user_id, chat_id)
        return

    LOGGER.info("processing chat %s from %r", chat_id, sender)

    async with SessionLocal() as session:
        dialog_service = DialogService(session)
        result = await dialog_service.handle_avito_message(
            client_id=client_id,
            avito_account_id=account_id,
            avito_dialog_id=chat_id,
            message_text=text,
            sender=sender,
            item_title=item_title,
        )
        LOGGER.info("dialog result: %s", result)

    if mark_read:
        await mark_chat_read(token, user_id, chat_id)
        LOGGER.info("marked chat %s as read", chat_id)


async def main(account_id: int, client_id: int, mark_read: bool) -> None:
    service = AvitoService()
    async with service._account_context(account_id) as (account, repo):
        token = await service._ensure_access_token(account, repo)
        user_id = await service._get_account_user_id(account.id, token)
        LOGGER.info("account %s, avito user_id %s", account.id, user_id)

    chats = await fetch_unread(token, user_id)
    if not chats:
        LOGGER.info("no unread chats")
        return

    for chat in chats:
        await process_chat(chat, client_id, account_id, token, user_id, mark_read=mark_read)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Одноразовый polling Avito Messenger API")
    parser.add_argument(
        "--account-id",
        type=int,
        default=os.getenv("TUBERRY_AVITO_ACCOUNT_ID"),
        required=True,
        help="ID записи в таблице avito_accounts",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=os.getenv("TUBERRY_CLIENT_ID"),
        required=True,
        help="ID клиента (clients.id), которому принадлежит диалог",
    )
    parser.add_argument(
        "--no-mark-read",
        action="store_true",
        help="Не помечать чат прочитанным после обработки",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            account_id=args.account_id,
            client_id=args.client_id,
            mark_read=not args.no_mark_read,
        )
    )
