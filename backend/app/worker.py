import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from app.db.session import SessionLocal
from app.models.enums import MessageStatus
from app.services.dialog import DialogService
from app.services.avito import AvitoService
from app.services.queue import TaskQueue
from app.services.telegram import TelegramService
from app.repositories.avito_repository import AvitoAccountRepository


def _first_non_empty(*values: Optional[Any]) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def _ensure_list(candidate: Any) -> List[Any]:
    if candidate is None:
        return []
    if isinstance(candidate, list):
        return candidate
    return [candidate]


def _build_message_from_value(value: dict[str, Any], *, fallback_item_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None

    content = value.get("content") if isinstance(value.get("content"), dict) else {}
    text = _first_non_empty(
        content.get("text"),
        content.get("value"),
        value.get("text"),
        value.get("body"),
    )

    attachments: List[Dict[str, Any]] = []
    attachments_block = content.get("attachments") if isinstance(content.get("attachments"), list) else []
    for item in attachments_block:
        if isinstance(item, dict):
            att_type = str(item.get("type") or item.get("kind") or "unknown").lower()
            attachments.append({"type": att_type, "payload": item})

    image_payload = content.get("image")
    if isinstance(image_payload, (dict, list)):
        attachments.append({"type": "image", "payload": image_payload})

    images_payload = content.get("images")
    if isinstance(images_payload, (dict, list)):
        attachments.append({"type": "image", "payload": images_payload})

    voice_payload = content.get("voice")
    if isinstance(voice_payload, dict):
        attachments.append(
            {
                "type": "voice",
                "voice_id": voice_payload.get("voice_id") or voice_payload.get("id"),
                "payload": voice_payload,
            }
        )

    dialog_id = _first_non_empty(
        value.get("chat_id"),
        value.get("chatId"),
        value.get("dialog_id"),
        value.get("conversation_id"),
    )
    if dialog_id is None:
        return None

    sender = _first_non_empty(
        value.get("author_name"),
        value.get("author_username"),
        value.get("author_id"),
        value.get("user_id"),
    )
    author_id = _first_non_empty(
        value.get("author_id"),
        value.get("user_id"),
    )

    item_title = _first_non_empty(
        fallback_item_title,
        value.get("item_title"),
    )
    if item_title is None:
        item_id = value.get("item_id")
        if item_id:
            item_title = f"Avito item {item_id}"

    message_type = value.get("type") or content.get("type")
    source_message_id = _first_non_empty(
        value.get("id"),
        value.get("message_id"),
        value.get("uuid"),
    )

    if not text and not attachments:
        logger.debug("Skipping Avito webhook message without textual or attachment content", message=value)
        return None

    return {
        "dialog_id": str(dialog_id),
        "text": text or "",
        "sender": str(sender) if sender is not None else None,
        "item_title": item_title,
        "attachments": attachments,
        "message_type": message_type,
        "source_message_id": str(source_message_id) if source_message_id else None,
        "author_id": str(author_id) if author_id is not None else None,
    }


def parse_avito_webhook_payload(body: Any) -> List[Dict[str, Any]]:
    if not isinstance(body, (dict, list)):
        return []

    entries = body if isinstance(body, list) else [body]
    results: List[Dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        payload = entry.get("payload")
        if isinstance(payload, dict):
            event_type = payload.get("type") or entry.get("type")
            if event_type == "message":
                value = payload.get("value")
                built = _build_message_from_value(value, fallback_item_title=None) if isinstance(value, dict) else None
                if built:
                    results.append(built)
                    continue

        payload_candidates: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("data", "value", "message"):
                candidate = payload.get(key)
                if isinstance(candidate, dict):
                    payload_candidates.append(candidate)
            payload_candidates.append(payload)
        else:
            payload_candidates.append(entry)

        seen_ids: set[str] = set()
        for base in payload_candidates:
            if not isinstance(base, dict):
                continue

            context = base.get("context")
            if isinstance(context, dict):
                context_value = context.get("value") if isinstance(context.get("value"), dict) else {}
            else:
                context_value = {}

            item_title = _first_non_empty(
                base.get("item_title"),
                base.get("title"),
                context_value.get("title"),
            )

            candidates = _ensure_list(base.get("messages"))
            if not candidates:
                candidates = [base]

            for candidate in candidates:
                built = _build_message_from_value(candidate, fallback_item_title=item_title)
                if built is None:
                    continue
                msg_id = built.get("source_message_id") or f"{built.get('dialog_id')}:{built.get('text')}"
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                results.append(built)

    return results


async def process_avito_webhook_message(payload: Dict[str, Any]) -> None:
    account_id = payload.get("account_id")
    body = payload.get("payload")
    client_id = payload.get("client_id")

    if account_id is None or body is None:
        logger.warning("Webhook payload missing account_id or payload", payload=payload)
        return

    try:
        account_id_int = int(account_id)
    except (TypeError, ValueError):
        logger.warning("Invalid account_id in webhook payload", payload=payload)
        return

    async with SessionLocal() as session:
        repo = AvitoAccountRepository(session)
        account = await repo.get(account_id_int)
        if account is None:
            logger.warning("Received webhook for unknown Avito account", account_id=account_id_int)
            return
        resolved_client_id = client_id or account.client_id
        if resolved_client_id is None:
            logger.warning("Avito account not attached to client", account_id=account.id)
            return

        dialog_service = DialogService(session)
        messages = parse_avito_webhook_payload(body)
        if not messages:
            logger.info(
                "Avito webhook payload did not contain parsable messages: {}",
                str(body)[:500],
                account_id=account.id,
            )
            return

        service = AvitoService()
        account_user_id: Optional[str] = None
        try:
            access_token = await service._ensure_access_token(account, repo)
            account_user_id = await service._get_account_user_id(account.id, access_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to resolve Avito account user id",
                account_id=account.id,
                error=str(exc),
            )

        for message in messages:
            try:
                author_id = message.get("author_id")
                if (
                    account_user_id is not None
                    and author_id is not None
                    and str(author_id) == str(account_user_id)
                ):
                    logger.debug(
                        "Skipping Avito echo message from account owner",
                        account_id=account.id,
                        dialog_id=message.get("dialog_id"),
                        author_id=author_id,
                    )
                    continue

                await dialog_service.handle_avito_message(
                    client_id=resolved_client_id,
                    avito_account_id=account.id,
                    avito_dialog_id=message["dialog_id"],
                    message_text=message.get("text"),
                    sender=message.get("sender"),
                    item_title=message.get("item_title"),
                    source_message_id=message.get("source_message_id"),
                    attachments=message.get("attachments"),
                    message_type=message.get("message_type"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Failed to process Avito webhook message",
                    account_id=account.id,
                    dialog_id=message.get("dialog_id"),
                    error=str(exc),
                )


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
        elif task_type == "avito.webhook_message":
            try:
                await process_avito_webhook_message(payload)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to process avito webhook message", error=str(exc), payload=payload)
        else:
            logger.warning("Unknown task type: {task_type}", task_type=task_type)


if __name__ == "__main__":
    asyncio.run(main())
