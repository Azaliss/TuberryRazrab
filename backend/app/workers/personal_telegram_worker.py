from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger
from telethon import events
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from app.core.config import settings
from app.core.crypto import decrypt_payload
from app.db.session import SessionLocal
from app.models.enums import MessageStatus, PersonalTelegramAccountStatus
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.personal_telegram_account_repository import PersonalTelegramAccountRepository
from app.services.personal_telegram_account import PersonalTelegramAccountService
from app.services.queue import TaskQueue


class PersonalTelegramWorker:
    def __init__(self) -> None:
        api_id, api_hash = settings.get_personal_telegram_credentials()
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_info = settings.get_personal_telegram_device_info()
        self._clients: Dict[int, TelegramClient] = {}
        self._handlers: Dict[int, Any] = {}
        self._lock = asyncio.Lock()

    async def run(self) -> None:
        logger.info("Personal Telegram worker started")
        await asyncio.gather(
            self._sync_loop(),
            self._queue_loop(),
        )

    async def _sync_loop(self) -> None:
        while True:
            try:
                await self._sync_accounts_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to synchronise personal telegram accounts", error=str(exc))
            await asyncio.sleep(15)

    async def _queue_loop(self) -> None:
        while True:
            try:
                task = await TaskQueue.dequeue_personal(timeout=5)
                if not task:
                    await asyncio.sleep(1)
                    continue
                task_type = task.get("type")
                payload = task.get("payload") or {}
                if task_type == "personal.send_message":
                    await self._handle_outbound(payload)
                else:
                    logger.warning("Unknown personal task type {}", task_type)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error while processing personal queue", error=str(exc))

    async def _sync_accounts_once(self) -> None:
        async with SessionLocal() as session:
            repo = PersonalTelegramAccountRepository(session)
            active_accounts = await repo.list_active()

        active_ids = {account.id for account in active_accounts}

        # stop clients that are no longer active
        for account_id in list(self._clients.keys()):
            if account_id not in active_ids:
                await self._stop_client(account_id)

        # start new clients
        for account in active_accounts:
            if account.session_payload is None:
                await self._mark_account_error(account.id, "Отсутствует сохранённая сессия")
                continue
            if account.id in self._clients:
                continue
            try:
                await self._start_client(account.id, account.session_payload)
                logger.info("Personal Telegram client started", account_id=account.id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to start personal telegram client", account_id=account.id, error=str(exc))
                await self._mark_account_error(account.id, f"Не удалось запустить сессию: {exc}")

    async def _start_client(self, account_id: int, session_payload: str) -> None:
        session_string = decrypt_payload(session_payload)
        client = TelegramClient(
            StringSession(session_string),
            self.api_id,
            self.api_hash,
            **self.device_info,
        )
        await client.connect()

        handler = self._make_event_handler(account_id)
        client.add_event_handler(handler, events.NewMessage(incoming=True))

        async with self._lock:
            self._clients[account_id] = client
            self._handlers[account_id] = handler

    async def _stop_client(self, account_id: int) -> None:
        async with self._lock:
            client = self._clients.pop(account_id, None)
            handler = self._handlers.pop(account_id, None)
        if client:
            if handler:
                try:
                    client.remove_event_handler(handler)
                except Exception:  # noqa: BLE001
                    pass
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            logger.info("Personal Telegram client stopped", account_id=account_id)

    def _make_event_handler(self, account_id: int):
        async def handler(event: events.NewMessage.Event) -> None:
            await self._handle_incoming_event(account_id, event)

        return handler

    async def _handle_incoming_event(self, account_id: int, event: events.NewMessage.Event) -> None:
        if event.message.out:
            return

        message_text = event.raw_text or ""
        if not message_text:
            return

        async with SessionLocal() as session:
            account_repo = PersonalTelegramAccountRepository(session)
            account = await account_repo.get(account_id)
            if account is None or account.status != PersonalTelegramAccountStatus.active:
                return

            if event.is_private and not account.accepts_private:
                return
            if event.is_group and not account.accepts_groups:
                return
            if event.is_channel and not account.accepts_channels:
                return

            service = PersonalTelegramAccountService(session)

            chat = await event.get_chat()
            sender = await event.get_sender()
            chat_id = str(getattr(chat, "id", event.chat_id))
            sender_name_parts = []
            if getattr(sender, "first_name", None):
                sender_name_parts.append(sender.first_name)
            if getattr(sender, "last_name", None):
                sender_name_parts.append(sender.last_name)
            sender_display = " ".join(sender_name_parts).strip() or getattr(sender, "username", None)

            try:
                await service.handle_incoming_message(
                    account=account,
                    chat_id=chat_id,
                    chat_type=getattr(chat, "title", None) or getattr(chat, "username", None) or "",
                    sender_id=getattr(sender, "id", None),
                    sender_display=sender_display,
                    message_text=message_text,
                    message_id=str(event.message.id),
                    date=event.message.date or datetime.utcnow(),
                )
                await account_repo.update(
                    account,
                    last_connected_at=datetime.utcnow(),
                    status=PersonalTelegramAccountStatus.active,
                    last_error=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to handle incoming personal telegram message", account_id=account_id, error=str(exc))

    async def _handle_outbound(self, payload: Dict[str, Any]) -> None:
        account_id = payload.get("account_id")
        dialog_id = payload.get("dialog_id")
        message_db_id = payload.get("message_db_id")
        text = (payload.get("text") or "").strip()

        if not account_id or not dialog_id or not text:
            logger.warning("Invalid outbound personal payload {}", payload)
            if message_db_id:
                async with SessionLocal() as session:
                    await MessageRepository(session).mark_status(message_db_id, MessageStatus.failed.value)
            return

        async with SessionLocal() as session:
            account_repo = PersonalTelegramAccountRepository(session)
            dialog_repo = DialogRepository(session)
            message_repo = MessageRepository(session)

            account = await account_repo.get(int(account_id))
            if account is None or account.status != PersonalTelegramAccountStatus.active:
                if message_db_id:
                    await message_repo.mark_status(message_db_id, MessageStatus.failed.value)
                return

            dialog = await dialog_repo.get(int(dialog_id))
            if dialog is None or dialog.external_reference is None:
                if message_db_id:
                    await message_repo.mark_status(message_db_id, MessageStatus.failed.value)
                return

            client = await self._ensure_client(account)
            if client is None:
                if message_db_id:
                    await message_repo.mark_status(message_db_id, MessageStatus.failed.value)
                return

            target = dialog.external_reference
            try:
                target_peer = int(target)
            except ValueError:
                target_peer = target

            try:
                await client.send_message(target_peer, text)
                if message_db_id:
                    await message_repo.mark_status(message_db_id, MessageStatus.delivered.value)
                await account_repo.update(
                    account,
                    last_connected_at=datetime.utcnow(),
                    last_error=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to send personal telegram message", account_id=account_id, dialog_id=dialog_id, error=str(exc))
                if message_db_id:
                    await message_repo.mark_status(message_db_id, MessageStatus.failed.value)

    async def _ensure_client(self, account) -> Optional[TelegramClient]:
        async with self._lock:
            client = self._clients.get(account.id)
        if client:
            return client
        if not account.session_payload:
            return None
        try:
            await self._start_client(account.id, account.session_payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restart personal telegram client", account_id=account.id, error=str(exc))
            return None
        async with self._lock:
            return self._clients.get(account.id)

    async def _mark_account_error(self, account_id: int, error_message: str) -> None:
        async with SessionLocal() as session:
            repo = PersonalTelegramAccountRepository(session)
            account = await repo.get(account_id)
            if account is None:
                return
            await repo.update(
                account,
                status=PersonalTelegramAccountStatus.error,
                last_error=error_message,
            )
        await self._stop_client(account_id)


async def main() -> None:
    worker = PersonalTelegramWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
