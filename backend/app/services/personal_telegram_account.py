from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import errors
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from app.core.config import settings
from app.core.crypto import encrypt_payload
from app.db.session import SessionLocal
from app.models.enums import (
    DialogSource,
    MessageDirection,
    MessageStatus,
    PersonalTelegramAccountStatus,
)
from app.models.personal_telegram_account import PersonalTelegramAccount
from app.repositories.bot_repository import BotRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.personal_telegram_account_repository import PersonalTelegramAccountRepository
from app.repositories.project_repository import ProjectRepository
from app.services.queue import TaskQueue
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)


@dataclass
class LoginSession:
    login_id: str
    client_id: int
    project_id: int
    qr_url: str
    created_at: datetime
    expires_at: datetime
    client: TelegramClient
    status: str = "pending"
    error: Optional[str] = None
    account_id: Optional[int] = None
    task: Optional[asyncio.Task[Any]] = None
    cleanup_task: Optional[asyncio.Task[Any]] = None
    password_prompted_at: Optional[datetime] = None


_LOGIN_SESSIONS: Dict[str, LoginSession] = {}
_LOGIN_LOCK = asyncio.Lock()


class PersonalTelegramAccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = PersonalTelegramAccountRepository(session)
        self.project_repo = ProjectRepository(session)
        self.dialog_repo = DialogRepository(session)
        self.message_repo = MessageRepository(session)
        self.bot_repo = BotRepository(session)

    # ------------------------------------------------------------------ #
    # Login management
    # ------------------------------------------------------------------ #
    async def start_login(self, *, project_id: int, client_id: int) -> LoginSession:
        api_id, api_hash = settings.get_personal_telegram_credentials()
        device_info = settings.get_personal_telegram_device_info()

        project = await self.project_repo.get(project_id)
        if project is None or project.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")

        login_id = uuid.uuid4().hex
        timeout = settings.personal_telegram_qr_timeout or 180
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(seconds=timeout)

        client = TelegramClient(
            StringSession(),
            api_id=api_id,
            api_hash=api_hash,
            **device_info,
        )
        await client.connect()

        try:
            qr_login = await client.qr_login()
        except Exception as exc:  # noqa: BLE001
            await client.disconnect()
            logger.exception("Failed to initiate QR login")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось инициировать QR-авторизацию") from exc

        session = LoginSession(
            login_id=login_id,
            client_id=client_id,
            project_id=project_id,
            qr_url=qr_login.url,
            created_at=created_at,
            expires_at=expires_at,
            client=client,
            status="ready",
        )

        async with _LOGIN_LOCK:
            _LOGIN_SESSIONS[login_id] = session

        session.task = asyncio.create_task(self._wait_for_login(session, qr_login, timeout))
        return session

    async def get_login_session(self, *, login_id: str, client_id: int) -> LoginSession:
        async with _LOGIN_LOCK:
            session = _LOGIN_SESSIONS.get(login_id)
        if session is None or session.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена или недоступна")
        return session

    async def submit_password(self, *, login_id: str, client_id: int, password: str) -> LoginSession:
        if not password.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пароль не может быть пустым")
        async with _LOGIN_LOCK:
            session = _LOGIN_SESSIONS.get(login_id)
        if session is None or session.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена или недоступна")
        if session.status != "password_required":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пароль не требуется для этой сессии")

        try:
            await session.client.sign_in(password=password)
        except errors.PasswordHashInvalidError:
            session.status = "password_required"
            session.error = "Неверный пароль"
            return session
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to complete login with password")
            session.status = "error"
            session.error = "Не удалось подтвердить пароль"
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось подтвердить пароль") from exc

        await self._finalize_login(session)
        try:
            await session.client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        if session.cleanup_task is None:
            session.cleanup_task = asyncio.create_task(self._schedule_cleanup(login_id))
        return session

    async def _wait_for_login(self, session: LoginSession, qr_login: Any, timeout: int) -> None:
        try:
            await asyncio.wait_for(qr_login.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            session.status = "expired"
            session.error = "Время действия QR-кода истекло"
        except errors.SessionPasswordNeededError:
            session.status = "password_required"
            session.error = None
            session.password_prompted_at = datetime.utcnow()
            if session.cleanup_task is None:
                session.cleanup_task = asyncio.create_task(self._schedule_cleanup(session.login_id))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("QR login failed")
            session.status = "error"
            session.error = str(exc)
        else:
            await self._finalize_login(session)
        finally:
            if session.status != "password_required":
                try:
                    await session.client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                if session.cleanup_task is None:
                    session.cleanup_task = asyncio.create_task(self._schedule_cleanup(session.login_id))

    async def _finalize_login(self, session: LoginSession) -> None:
        try:
            me = await session.client.get_me()
            string_session = session.client.session.save()
            encrypted_session = encrypt_payload(string_session)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to finalize login session")
            session.status = "error"
            session.error = f"Не удалось завершить авторизацию: {exc}"
            return

        async with SessionLocal() as db_session:
            account_repo = PersonalTelegramAccountRepository(db_session)
            project_repo = ProjectRepository(db_session)

            project = await project_repo.get(session.project_id)
            if project is None or project.client_id != session.client_id:
                session.status = "error"
                session.error = "Проект недоступен"
                return

            display_name = getattr(me, "first_name", None) or getattr(me, "last_name", None)
            if display_name and getattr(me, "last_name", None):
                display_name = f"{me.first_name} {me.last_name}".strip()
            elif getattr(me, "username", None):
                display_name = f"@{me.username}"

            account = await account_repo.create(
                client_id=session.client_id,
                project_id=session.project_id,
                display_name=display_name,
                username=getattr(me, "username", None),
                phone=getattr(me, "phone", None),
                session_payload=encrypted_session,
            )
            account = await account_repo.update(
                account,
                status=PersonalTelegramAccountStatus.active,
                telegram_user_id=str(getattr(me, "id", "")) if getattr(me, "id", None) else None,
                last_connected_at=datetime.utcnow(),
            )

        session.status = "completed"
        session.account_id = account.id
        session.error = None

    async def _schedule_cleanup(self, login_id: str, delay: int = 300) -> None:
        await asyncio.sleep(delay)
        async with _LOGIN_LOCK:
            session = _LOGIN_SESSIONS.pop(login_id, None)
        if session is None:
            return
        if session.task and not session.task.done():
            session.task.cancel()
        if session.client:
            try:
                await session.client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    # CRUD operations
    # ------------------------------------------------------------------ #
    async def list_accounts(self, *, client_id: int, project_id: Optional[int] = None) -> list[PersonalTelegramAccount]:
        if project_id is not None:
            project = await self.project_repo.get(project_id)
            if project is None or project.client_id != client_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
            return await self.account_repo.list_for_project(project_id)
        return await self.account_repo.list_for_client(client_id)

    async def get_account(self, *, account_id: int, client_id: int) -> PersonalTelegramAccount:
        account = await self.account_repo.get(account_id)
        if account is None or account.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")
        return account

    async def update_account(
        self,
        *,
        account: PersonalTelegramAccount,
        display_name: Optional[str] = None,
        accepts_private: Optional[bool] = None,
        accepts_groups: Optional[bool] = None,
        accepts_channels: Optional[bool] = None,
    ) -> PersonalTelegramAccount:
        updates: Dict[str, Any] = {}
        if display_name is not None:
            cleaned = display_name.strip()
            updates["display_name"] = cleaned or None
        if accepts_private is not None:
            updates["accepts_private"] = bool(accepts_private)
        if accepts_groups is not None:
            updates["accepts_groups"] = bool(accepts_groups)
        if accepts_channels is not None:
            updates["accepts_channels"] = bool(accepts_channels)
        if not updates:
            return account
        return await self.account_repo.update(account, **updates)

    async def delete_account(self, *, account: PersonalTelegramAccount) -> None:
        dialogs = await self.dialog_repo.list_for_personal_account(account.id)
        now = datetime.utcnow()
        for dialog in dialogs:
            dialog.personal_account_id = None
            dialog.external_display_name = dialog.external_display_name or account.display_name
            dialog.updated_at = now
        if dialogs:
            await self.session.commit()
        await self.account_repo.delete(account)

    # ------------------------------------------------------------------ #
    # Messaging integration (implemented during later stages)
    # ------------------------------------------------------------------ #
    async def handle_manager_reply(
        self,
        *,
        dialog_id: int,
        message_id: int,
        project_id: int | None,
        account: PersonalTelegramAccount,
        text: str,
    ) -> Dict[str, Any]:
        """Enqueue outbound message for personal Telegram account."""
        payload = {
            "account_id": account.id,
            "dialog_id": dialog_id,
            "message_db_id": message_id,
            "text": text,
            "project_id": project_id,
        }
        await TaskQueue.enqueue_personal("personal.send_message", payload)
        return {"queued": True}

    async def handle_incoming_message(
        self,
        *,
        account: PersonalTelegramAccount,
        chat_id: str,
        chat_type: str,
        sender_id: int | None,
        sender_display: str | None,
        message_text: str,
        message_id: str,
        date: datetime,
    ) -> Dict[str, Any]:
        """Persist incoming message and deliver it to operators' working group."""
        project = await self.project_repo.get(account.project_id) if account.project_id else None
        bot = await self.bot_repo.get(project.bot_id) if project and project.bot_id else None
        if bot is None or not bot.group_chat_id:
            logger.warning("Personal account %s has no bound controller bot", account.id)
            return {"ignored": True, "reason": "no_controller_bot"}

        dialog = await self.dialog_repo.get_by_personal_account(
            personal_account_id=account.id,
            external_reference=chat_id,
        )
        if dialog is None:
            manager_service = TelegramService(bot.token)
            topic_name = sender_display or chat_id
            try:
                created_topic = await manager_service.create_topic(bot.group_chat_id, topic_name[:128])
                thread_id = str(created_topic.get("message_thread_id"))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to create topic for personal telegram dialog", account_id=account.id)
                return {"ignored": True, "reason": "topic_creation_failed", "error": str(exc)}

            dialog = await self.dialog_repo.create(
                client_id=account.client_id,
                project_id=project.id if project else None,
                bot_id=bot.id,
                avito_dialog_id=f"ptg:{account.id}:{chat_id}",
                avito_account_id=None,
                source=DialogSource.personal_telegram,
                telegram_chat_id=bot.group_chat_id,
                telegram_topic_id=str(created_topic.get("message_thread_id")),
                personal_account_id=account.id,
                external_reference=chat_id,
                external_display_name=sender_display,
                external_username=None,
            )

        message = await self.message_repo.create(
            dialog_id=dialog.id,
            direction=MessageDirection.personal_telegram_in.value,
            source_message_id=message_id,
            body=message_text,
            status=MessageStatus.delivered.value,
            is_client_message=True,
        )

        await self.dialog_repo.touch(dialog)

        if bot and bot.token and (dialog.telegram_chat_id or bot.group_chat_id):
            manager_service = TelegramService(bot.token)
            try:
                await manager_service.send_message(
                    chat_id=dialog.telegram_chat_id or bot.group_chat_id,
                    text=f"💬 {sender_display or 'Клиент'}: {message_text}",
                    message_thread_id=int(dialog.telegram_topic_id) if dialog.telegram_topic_id else None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to mirror personal telegram inbound message", error=str(exc))

        return {"message_id": message.id}
