from typing import Any, Dict, Optional

import httpx

from app.core.config import settings


class TelegramService:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"{settings.telegram_api_base}/bot{token}"

    async def _post(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.base_url}/{method}", json=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok", False):
                raise ValueError(data)
            return data["result"]

    async def get_me(self) -> Dict[str, Any]:
        return await self._post("getMe", {})

    async def get_chat(self, chat_id: str) -> Dict[str, Any]:
        return await self._post("getChat", {"chat_id": chat_id})

    async def send_message(
        self,
        chat_id: str,
        text: str,
        message_thread_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        return await self._post("sendMessage", payload)

    async def send_photo(
        self,
        *,
        chat_id: str,
        photo: str | tuple[bytes, str, str | None],
        caption: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        if isinstance(photo, str):
            payload: Dict[str, Any] = {"chat_id": chat_id, "photo": photo}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if message_thread_id is not None:
                payload["message_thread_id"] = message_thread_id
            return await self._post("sendPhoto", payload)

        data, filename, content_type = self._normalize_file_payload(photo)
        form: Dict[str, Any] = {"chat_id": chat_id}
        if caption:
            form["caption"] = caption
        if parse_mode:
            form["parse_mode"] = parse_mode
        if message_thread_id is not None:
            form["message_thread_id"] = str(message_thread_id)

        files = {"photo": (filename or "photo.jpg", data, content_type or "application/octet-stream")}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/sendPhoto", data=form, files=files)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise ValueError(payload)
        return payload["result"]

    async def send_voice(
        self,
        *,
        chat_id: str,
        voice: str | tuple[bytes, str, str | None],
        caption: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        duration: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        if isinstance(voice, str):
            payload: Dict[str, Any] = {"chat_id": chat_id, "voice": voice}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if message_thread_id is not None:
                payload["message_thread_id"] = message_thread_id
            if duration is not None:
                payload["duration"] = duration
            return await self._post("sendVoice", payload)

        data, filename, content_type = self._normalize_file_payload(voice)
        form: Dict[str, Any] = {"chat_id": chat_id}
        if caption:
            form["caption"] = caption
        if parse_mode:
            form["parse_mode"] = parse_mode
        if message_thread_id is not None:
            form["message_thread_id"] = str(message_thread_id)
        if duration is not None:
            form["duration"] = str(duration)

        files = {"voice": (filename or "voice.ogg", data, content_type or "application/octet-stream")}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/sendVoice", data=form, files=files)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise ValueError(payload)
        return payload["result"]

    async def send_document(
        self,
        *,
        chat_id: str,
        document: str | tuple[bytes, str, str | None],
        caption: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        if isinstance(document, str):
            payload: Dict[str, Any] = {"chat_id": chat_id, "document": document}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if message_thread_id is not None:
                payload["message_thread_id"] = message_thread_id
            return await self._post("sendDocument", payload)

        data, filename, content_type = self._normalize_file_payload(document)
        form: Dict[str, Any] = {"chat_id": chat_id}
        if caption:
            form["caption"] = caption
        if parse_mode:
            form["parse_mode"] = parse_mode
        if message_thread_id is not None:
            form["message_thread_id"] = str(message_thread_id)

        files = {"document": (filename or "file.bin", data, content_type or "application/octet-stream")}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/sendDocument", data=form, files=files)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise ValueError(payload)
        return payload["result"]

    async def download_file(self, file_id: str) -> tuple[bytes, str | None, str | None]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/getFile", params={"file_id": file_id})
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise ValueError(payload)
        result = payload["result"]
        file_path = result.get("file_path")
        file_unique_id = result.get("file_unique_id")
        if not file_path:
            raise ValueError("file_path is missing in getFile response")

        download_url = f"{settings.telegram_api_base}/file/bot{self.token}/{file_path}"
        async with httpx.AsyncClient(timeout=30) as client:
            file_response = await client.get(download_url)
            file_response.raise_for_status()
            content = file_response.content
            content_type = file_response.headers.get("content-type")

        filename = file_path.split("/")[-1] if file_path else file_unique_id
        return content, filename, content_type

    @staticmethod
    def _normalize_file_payload(
        payload: tuple[bytes, str, str | None]
    ) -> tuple[bytes, Optional[str], Optional[str]]:
        if not isinstance(payload, tuple) or len(payload) not in {2, 3}:
            raise ValueError("File payload must be a tuple of (data, filename[, content_type])")
        data = payload[0]
        filename = payload[1] if len(payload) > 1 else None
        content_type = payload[2] if len(payload) > 2 else None
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("File payload data must be bytes")
        return bytes(data), filename, content_type

    async def create_topic(self, chat_id: str, name: str) -> Dict[str, Any]:
        return await self._post("createForumTopic", {"chat_id": chat_id, "name": name[:128]})

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: Optional[str] = None,
        allowed_updates: Optional[list[str]] = None,
        drop_pending_updates: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates
        if drop_pending_updates:
            payload["drop_pending_updates"] = True
        return await self._post("setWebhook", payload)

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"drop_pending_updates": drop_pending_updates}
        return await self._post("deleteWebhook", payload)

    async def delete_forum_topic(self, chat_id: str, message_thread_id: int) -> Dict[str, Any]:
        return await self._post(
            "deleteForumTopic",
            {"chat_id": chat_id, "message_thread_id": message_thread_id},
        )

    async def delete_message(self, chat_id: str, message_id: int) -> Dict[str, Any]:
        return await self._post(
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
        )

    async def edit_topic_name(
        self,
        chat_id: str,
        message_thread_id: int,
        name: str,
    ) -> Dict[str, Any]:
        return await self._post(
            "editForumTopic",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "name": name[:128],
            },
        )

    async def get_forum_topic_list(
        self,
        chat_id: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id}
        if offset is not None:
            payload["offset"] = offset
        if limit is not None:
            payload["limit"] = limit
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/getForumTopicList", params=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok", False):
                raise ValueError(data)
            return data["result"]

    async def pin_message(
        self,
        chat_id: str,
        message_id: int,
        message_thread_id: Optional[int] = None,
        disable_notification: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": disable_notification,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        return await self._post("pinChatMessage", payload)
