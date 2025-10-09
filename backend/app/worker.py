import asyncio
from typing import Any, Dict

from loguru import logger

from app.db.session import SessionLocal
from app.models.enums import MessageStatus
from app.services.dialog import DialogService
from app.services.avito import AvitoService
from app.services.queue import TaskQueue
from app.services.telegram import TelegramService


async def finalize_outbound_status(payload: Dict[str, Any], default_status: str = "outgoing") -> None:
    account_id = payload.get("account_id")
    avito_dialog_id = payload.get("dialog_id")
    message_db_id = payload.get("message_db_id")
    chat_id = payload.get("telegram_chat_id")
    topic_id = payload.get("telegram_topic_id")
    bot_token = payload.get("bot_token")
    status_label = payload.get("status_on_success") or default_status

    if account_id is None or avito_dialog_id is None:
        logger.debug("Skipping outbound status update due to missing account or dialog id", payload=payload)
        return

    try:
        account_id_int = int(account_id)
    except (TypeError, ValueError):
        logger.warning("Invalid account_id in payload, skipping status update", payload=payload)
        return

    async with SessionLocal() as session:
        service = DialogService(session)

        if message_db_id is not None:
            try:
                message_db_id_int = int(message_db_id)
            except (TypeError, ValueError):
                logger.warning("Invalid message_db_id in payload", payload=payload)
            else:
                try:
                    await service.message_repo.mark_status(message_db_id_int, MessageStatus.delivered.value)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to mark message as delivered",
                        message_id=message_db_id_int,
                        error=str(exc),
                    )

        dialog = await service.dialog_repo.get_by_account_and_avito_id(account_id_int, str(avito_dialog_id))
        if dialog is None:
            logger.warning(
                "Unable to locate dialog for outbound status update",
                account_id=account_id,
                avito_dialog_id=avito_dialog_id,
            )
            return

        chat_id = chat_id or dialog.telegram_chat_id
        topic_id = topic_id or dialog.telegram_topic_id
        if not chat_id or not topic_id:
            logger.info(
                "Skipping topic status update due to missing chat/topic binding",
                dialog_id=dialog.id,
            )
            return

        bot_token_to_use = bot_token
        if not bot_token_to_use:
            bot = await service.bot_repo.get(dialog.bot_id)
            bot_token_to_use = getattr(bot, "token", None)
        if not bot_token_to_use:
            logger.info("Bot token not available for dialog", dialog_id=dialog.id)
            return

        tg = TelegramService(bot_token_to_use)
        item_title = payload.get("topic_item_title")
        if not item_title:
            try:
                item_title, _, _, _ = await service._resolve_item_title_and_url(
                    avito_account_id=dialog.avito_account_id,
                    avito_dialog_id=dialog.avito_dialog_id,
                    current=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to resolve item title for dialog",
                    dialog_id=dialog.id,
                    error=str(exc),
                )
                item_title = None

        safe_topic_id = dialog.telegram_topic_id or topic_id
        status_value = status_label if status_label in {"incoming", "outgoing", "auto"} else default_status
        try:
            await service._update_topic_status(
                tg,
                chat_id=str(chat_id),
                topic_id=str(safe_topic_id),
                item_title=item_title or f"Диалог {dialog.avito_dialog_id}",
                status=status_value,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to apply topic status after outbound send",
                dialog_id=dialog.id,
                error=str(exc),
            )


async def handle_outbound_failure(payload: Dict[str, Any]) -> None:
    account_id = payload.get("account_id")
    avito_dialog_id = payload.get("dialog_id")
    message_db_id = payload.get("message_db_id")

    if account_id is None or avito_dialog_id is None:
        return

    try:
        account_id_int = int(account_id)
    except (TypeError, ValueError):
        return

    async with SessionLocal() as session:
        service = DialogService(session)

        if message_db_id is not None:
            try:
                message_db_id_int = int(message_db_id)
            except (TypeError, ValueError):
                message_db_id_int = None
            if message_db_id_int is not None:
                try:
                    await service.message_repo.mark_status(message_db_id_int, MessageStatus.failed.value)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to mark message as failed after outbound error",
                        message_id=message_db_id_int,
                        error=str(exc),
                    )

        dialog = await service.dialog_repo.get_by_account_and_avito_id(account_id_int, str(avito_dialog_id))
        if dialog is None:
            return

        bot = await service.bot_repo.get(dialog.bot_id)
        bot_token = getattr(bot, "token", None)
        if not bot_token or not dialog.telegram_chat_id or not dialog.telegram_topic_id:
            return

        tg = TelegramService(bot_token)
        try:
            await service._update_topic_status(
                tg,
                chat_id=str(dialog.telegram_chat_id),
                topic_id=str(dialog.telegram_topic_id),
                item_title=f"Диалог {dialog.avito_dialog_id}",
                status="incoming",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to revert topic status after outbound error",
                dialog_id=dialog.id,
                error=str(exc),
            )


async def main() -> None:
    logger.info("Worker started")
    avito = AvitoService()
    while True:
        task = await TaskQueue.dequeue(timeout=5)
        if task is None:
            await asyncio.sleep(1)
            continue
        task_type = task.get("type")
        payload = task.get("payload", {})
        logger.info("Processing task {task_type}", task_type=task_type)
        if task_type == "avito.send_message":
            try:
                kind = (payload.get("kind") or "text").lower()
                account_id = payload.get("account_id")
                dialog_id = payload.get("dialog_id")

                if kind == "text":
                    result = await avito.send_message(
                        account_id=account_id,
                        dialog_id=dialog_id,
                        text=payload.get("text") or "",
                    )
                elif kind == "image":
                    file_id = payload.get("file_id")
                    bot_token = payload.get("bot_token")
                    if not bot_token or not file_id:
                        logger.error(
                            "Image task missing bot_token or file_id",
                            payload=payload,
                        )
                        continue
                    tg_service = TelegramService(bot_token)
                    file_bytes, filename, content_type = await tg_service.download_file(file_id)
                    image_id = await avito.upload_image(
                        account_id=account_id,
                        file_name=filename or "image.jpg",
                        file_bytes=file_bytes,
                        content_type=content_type,
                    )
                    result = await avito.send_image_message(
                        account_id=account_id,
                        dialog_id=dialog_id,
                        image_id=image_id,
                    )
                else:
                    logger.warning("Unsupported avito.send_message kind: %s", kind, payload=payload)
                    continue

                avito_message_id = result.get("message_id")
                if avito_message_id:
                    await TaskQueue.remember_outbound_message(
                        avito_message_id,
                        account_id=account_id,
                        dialog_id=str(dialog_id),
                    )
                await finalize_outbound_status(payload)
                logger.info("Avito message sent", payload=payload, result=result)
            except Exception as exc:  # noqa: BLE001 - логируем любую ошибку, чтобы воркер не падал
                logger.exception("Failed to send message to Avito", error=str(exc), payload=payload)
                await handle_outbound_failure(payload)
        else:
            logger.warning("Unknown task type: {task_type}", task_type=task_type)


if __name__ == "__main__":
    asyncio.run(main())
