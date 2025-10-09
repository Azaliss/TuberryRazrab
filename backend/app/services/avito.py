from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Sequence
from urllib.parse import quote

import httpx
from loguru import logger

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.avito import AvitoAccount
from app.repositories.avito_repository import AvitoAccountRepository

TOKEN_LEEWAY_SECONDS = 60


class AvitoService:
    """Обёртка над Avito Messenger API."""

    def __init__(self) -> None:
        self._user_cache: dict[int, str] = {}

    @staticmethod
    def extract_message_id(payload: Dict[str, Any] | None) -> str | None:
        if not isinstance(payload, dict):
            return None

        candidates: list[Any] = []
        for key in ("id", "message_id", "messageId", "uuid"):
            if key in payload:
                candidates.append(payload[key])

        nested = payload.get("message")
        if isinstance(nested, dict):
            for key in ("id", "message_id", "messageId"):
                if key in nested:
                    candidates.append(nested[key])

        result_block = payload.get("result")
        if isinstance(result_block, dict):
            for key in ("id", "message_id", "messageId"):
                if key in result_block:
                    candidates.append(result_block[key])

        for candidate in candidates:
            if candidate:
                return str(candidate)
        return None

    async def send_message(self, account_id: int, dialog_id: str, text: str) -> Dict[str, Any]:
        if account_id is None:
            raise ValueError("account_id is required")
        if not dialog_id:
            raise ValueError("dialog_id is required")
        if not text:
            raise ValueError("text is required")

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.post(
                f"/messenger/v1/accounts/{user_id}/chats/{quote(str(dialog_id), safe='')}/messages",
                json={"type": "text", "message": {"text": text}},
                headers=self._build_headers(access_token),
            )
            response.raise_for_status()
            payload = response.json()

        logger.info(
            "Sent message to Avito: %s",
            payload,
            account_id=account_id,
            dialog_id=dialog_id,
        )

        message_id = self.extract_message_id(payload)

        return {
            "status": "sent",
            "dialog_id": str(dialog_id),
            "account_id": account_id,
            "response": payload,
            "message_id": message_id,
        }

    async def send_image_message(self, account_id: int, dialog_id: str, image_id: str) -> Dict[str, Any]:
        if account_id is None:
            raise ValueError("account_id is required")
        if not dialog_id:
            raise ValueError("dialog_id is required")
        if not image_id:
            raise ValueError("image_id is required")

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.post(
                f"/messenger/v1/accounts/{user_id}/chats/{quote(str(dialog_id), safe='')}/messages/image",
                json={"image_id": image_id},
                headers=self._build_headers(access_token),
            )
            response.raise_for_status()
            payload = response.json()

        message_id = self.extract_message_id(payload)

        return {
            "status": "sent",
            "dialog_id": str(dialog_id),
            "account_id": account_id,
            "response": payload,
            "message_id": message_id,
        }

    async def upload_image(
        self,
        account_id: int,
        *,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None = None,
    ) -> str:
        if account_id is None:
            raise ValueError("account_id is required")
        if not file_bytes:
            raise ValueError("file_bytes is empty")

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        files = {
            "uploadfile[]": (
                file_name or "image.jpg",
                file_bytes,
                content_type or "application/octet-stream",
            )
        }

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=30.0) as client:
            response = await client.post(
                f"/messenger/v1/accounts/{user_id}/uploadImages",
                headers={"Authorization": f"Bearer {access_token}"},
                files=files,
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict) or not payload:
            raise ValueError("Unexpected response payload from uploadImages")

        image_id = next(iter(payload.keys()))
        if not image_id:
            raise ValueError("Failed to extract image_id from uploadImages response")
        return image_id

    async def acknowledge_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        account_id = payload.get("account_id")
        dialog_id = payload.get("dialog_id")
        if account_id is None or dialog_id is None:
            raise ValueError("`account_id` and `dialog_id` are required in payload")

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.post(
                f"/messenger/v1/accounts/{user_id}/chats/{quote(str(dialog_id), safe='')}/read",
                headers=self._build_headers(access_token),
            )
            response.raise_for_status()

        logger.info("Marked Avito chat as read", account_id=account_id, dialog_id=dialog_id)
        return {"status": "ok", "dialog_id": str(dialog_id)}

    async def get_chat_metadata(self, account_id: int, dialog_id: str) -> Dict[str, Any]:
        if account_id is None or not dialog_id:
            raise ValueError("account_id and dialog_id are required")

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.get(
                f"/messenger/v2/accounts/{user_id}/chats/{quote(str(dialog_id), safe='')}",
                headers=self._build_headers(access_token),
            )
            response.raise_for_status()
            payload = response.json()

        return payload

    async def list_orders(
        self,
        account_id: int,
        *,
        statuses: Sequence[str] | None = None,
        date_from: int | None = None,
        page_limit: int = 20,
    ) -> list[Dict[str, Any]]:
        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)

        params_base: list[tuple[str, str]] = []
        if statuses:
            for status in statuses:
                params_base.append(("statuses", status))
        if date_from is not None:
            params_base.append(("dateFrom", str(int(date_from))))

        orders: list[Dict[str, Any]] = []
        page = 1
        while True:
            params = list(params_base)
            params.append(("page", str(page)))
            params.append(("limit", str(page_limit)))

            async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
                response = await client.get(
                    "/order-management/1/orders",
                    params=params,
                    headers=self._build_headers(access_token),
                )
                response.raise_for_status()
                payload = response.json()

            batch = payload.get("orders") or []
            orders.extend(batch)

            if not payload.get("hasMore"):
                break
            page += 1

        return orders

    async def get_voice_file_urls(self, account_id: int, voice_ids: Sequence[str]) -> Dict[str, str]:
        if account_id is None:
            raise ValueError("account_id is required")
        voice_ids = [vid for vid in voice_ids if vid]
        if not voice_ids:
            return {}

        async with self._account_context(int(account_id)) as (account, repo):
            access_token = await self._ensure_access_token(account, repo)
            user_id = await self._get_account_user_id(account.id, access_token)

        params: list[tuple[str, str]] = [("voice_ids", str(voice_id)) for voice_id in voice_ids]

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.get(
                f"/messenger/v1/accounts/{user_id}/getVoiceFiles",
                params=params,
                headers=self._build_headers(access_token),
            )
            response.raise_for_status()
            payload = response.json()

        voices = payload.get("voices_urls")
        if isinstance(voices, dict):
            return {str(key): value for key, value in voices.items() if isinstance(value, str)}
        return {}

    @asynccontextmanager
    async def _account_context(
        self, account_id: int
    ) -> tuple[AvitoAccount, AvitoAccountRepository]:
        async with SessionLocal() as session:
            repo = AvitoAccountRepository(session)
            account = await repo.get(account_id)
            if account is None:
                raise ValueError("Avito account not found")
            yield account, repo

    async def _ensure_access_token(
        self, account: AvitoAccount, repo: AvitoAccountRepository
    ) -> str:
        if (
            account.access_token
            and account.token_expires_at
            and account.token_expires_at > datetime.utcnow() + timedelta(seconds=TOKEN_LEEWAY_SECONDS)
        ):
            return account.access_token
        refreshed = await self._refresh_access_token(account, repo)
        return refreshed

    async def _refresh_access_token(
        self, account: AvitoAccount, repo: AvitoAccountRepository
    ) -> str:
        if not account.api_client_id or not account.api_client_secret:
            raise ValueError("Avito account credentials are not configured")

        data = {
            "grant_type": "client_credentials",
            "client_id": account.api_client_id,
            "client_secret": account.api_client_secret,
        }

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.post("/token", data=data)
            response.raise_for_status()
            token_payload = response.json()

        access_token = token_payload.get("access_token")
        if not access_token:
            raise ValueError("Avito token response does not contain access_token")

        expires_in = token_payload.get("expires_in")
        ttl = int(expires_in) if expires_in is not None else 3600
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        updated_account = await repo.update(
            account,
            access_token=access_token,
            token_expires_at=expires_at,
        )

        # Сбросим кеш user_id, чтобы в следующем вызове он переинициализировался при необходимости
        self._user_cache.pop(updated_account.id, None)

        return updated_account.access_token or access_token

    async def _get_account_user_id(self, account_id: int, access_token: str) -> str:
        cached = self._user_cache.get(account_id)
        if cached:
            return cached

        async with httpx.AsyncClient(base_url=settings.avito_api_base, timeout=15.0) as client:
            response = await client.get("/core/v1/accounts/self", headers=self._build_headers(access_token))
            response.raise_for_status()
            data = response.json()

        user_id = data.get("id")
        if not user_id:
            raise ValueError("Avito /core/v1/accounts/self response does not contain id")

        user_id_str = str(user_id)
        self._user_cache[account_id] = user_id_str
        return user_id_str

    @staticmethod
    def _build_headers(access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
