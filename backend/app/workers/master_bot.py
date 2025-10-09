import asyncio
from typing import Any, Dict

import httpx
from loguru import logger

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.project_settings_repository import ProjectSettingsRepository


class MasterBot:
    def __init__(self) -> None:
        self.token: str | None = None
        self.api_base: str | None = None
        self.backend_base = settings.backend_internal_url.rstrip("/")
        self.frontend_base = settings.frontend_base_url.rstrip("/")
        self.offset = 0

    async def poll(self) -> None:
        logger.info("Master bot polling started")
        async with httpx.AsyncClient(timeout=20) as client:
            while True:
                token = await self._load_token()
                if not token:
                    logger.warning("MASTER_BOT_TOKEN не задан, ожидание настроек...")
                    await asyncio.sleep(10)
                    continue

                if token != self.token:
                    self.token = token
                    self.api_base = f"{settings.telegram_api_base}/bot{self.token}"
                    self.offset = 0
                    logger.info("Master bot token обновлён")

                try:
                    response = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={"timeout": 15, "offset": self.offset + 1},
                    )
                    response.raise_for_status()
                    data = response.json()
                    for update in data.get("result", []):
                        self.offset = update["update_id"]
                        await self._handle_update(client, update)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Polling error: {exc}", exc=exc)
                    await asyncio.sleep(5)

    async def _handle_update(self, client: httpx.AsyncClient, update: Dict[str, Any]) -> None:
        message = update.get("message")
        if not message:
            return
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        if text.startswith("/start"):
            await self._send_login_link(client, chat_id, message)
        else:
            await self._reply(client, chat_id, "Отправьте /start для получения ссылки в кабинет.")

    async def _send_login_link(self, client: httpx.AsyncClient, chat_id: int, message: Dict[str, Any]) -> None:
        telegram_user_id = str(message["from"]["id"])
        async with httpx.AsyncClient(base_url=self.backend_base, timeout=10) as backend:
            resp = await backend.post(
                "/api/auth/master/link",
                json={"telegram_user_id": telegram_user_id, "role": "owner"},
            )
            resp.raise_for_status()
            body = resp.json()
        token = body["link_token"]
        login_url = f"{self.frontend_base}/login?token={token}"
        text = (
            "Добро пожаловать в Tuberry!\n\n"
            "1. Перейдите по ссылке: {url}\n"
            "2. Авторизуйтесь в кабинете."
        ).format(url=login_url)
        await self._reply(client, chat_id, text)

    async def _reply(self, client: httpx.AsyncClient, chat_id: int, text: str) -> None:
        await client.post(f"{self.api_base}/sendMessage", json={"chat_id": chat_id, "text": text})

    async def _load_token(self) -> str | None:
        async with SessionLocal() as session:
            repo = ProjectSettingsRepository(session)
            settings_obj = await repo.get()
            return settings_obj.master_bot_token


async def main() -> None:
    bot = MasterBot()
    await bot.poll()


if __name__ == "__main__":
    asyncio.run(main())
