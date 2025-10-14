import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api import deps
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.bot_repository import BotRepository
from app.repositories.telegram_chat_repository import TelegramChatRepository
from app.services.dialog import DialogService
from app.services.queue import TaskQueue
from app.services.telegram import TelegramService

router = APIRouter()


@router.post("/avito/messages/{account_id}/{secret}")
async def avito_message_webhook(
    account_id: int,
    secret: str,
    request: Request,
    session: AsyncSession = Depends(deps.get_db),
):
    repo = AvitoAccountRepository(session)
    account = await repo.get(account_id)
    if account is None or account.webhook_secret != secret:
        logger.warning(
            "Avito webhook attempt with invalid credentials",
            account_id=account_id,
        )
        raise HTTPException(status_code=404, detail="Webhook not registered")

    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Invalid JSON payload from Avito webhook",
            account_id=account.id,
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    logger.info("Received Avito webhook payload: {}", str(payload)[:500], account_id=account.id)

    await TaskQueue.enqueue(
        "avito.webhook_message",
        {
            "account_id": account.id,
            "client_id": account.client_id,
            "payload": payload,
        },
    )
    return {"status": "accepted"}


@router.post("/telegram/{bot_id}/{secret}")
async def telegram_webhook(
    bot_id: int,
    secret: str,
    request: Request,
    session: AsyncSession = Depends(deps.get_db),
):
    repo = BotRepository(session)
    bot = await repo.get(bot_id)
    if bot is None:
        print("[webhook] bot not found", bot_id)
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.webhook_secret != secret:
        print("[webhook] secret mismatch", bot_id, secret, bot.webhook_secret)
        raise HTTPException(status_code=404, detail="Bot not found")
    bot_token = bot.token
    payload = await request.json()

    membership_update = payload.get("my_chat_member")
    if membership_update:
        result = await _handle_my_chat_member_update(
            session=session,
            bot=bot,
            update=membership_update,
        )
        return {"status": "ok", "data": result}

    message = payload.get("message") or payload.get("channel_post")
    if not message:
        return {"status": "ignored"}

    message_id_value = message.get("message_id")
    chat = message.get("chat", {})
    chat_id_value = chat.get("id")
    chat_id = str(chat_id_value) if chat_id_value is not None else None

    if message.get("forum_topic_edited"):
        if chat_id is None or message_id_value is None:
            return {"status": "ignored", "reason": "forum_topic_edit_missing_ids"}

        try:
            message_id_int = int(message_id_value)
        except (TypeError, ValueError):
            message_id_int = None

        if message_id_int is None:
            return {"status": "ignored", "reason": "forum_topic_edit_bad_message_id"}

        tg_service = TelegramService(bot_token)
        try:
            await tg_service.delete_message(chat_id=chat_id, message_id=message_id_int)
        except Exception as exc:  # noqa: BLE001
            try:
                await asyncio.sleep(0.4)
                await tg_service.delete_message(chat_id=chat_id, message_id=message_id_int)
            except Exception as retry_exc:  # noqa: BLE001
                print(
                    "[webhook] failed to delete forum topic edited message",
                    {
                        "bot_id": bot_id,
                        "chat_id": chat_id,
                        "message_id": message_id_int,
                        "error": str(exc),
                        "retry_error": str(retry_exc),
                    },
                )
                return {
                    "status": "ignored",
                    "reason": "forum_topic_edit_delete_failed",
                    "chat_id": chat_id,
                }
        return {
            "status": "ok",
            "action": "forum_topic_edit_deleted",
            "chat_id": chat_id,
            "message_id": message_id_int,
        }

    text = message.get("text") or message.get("caption")

    sender = message.get("from") or {}
    if sender.get("is_bot"):
        return {"status": "ignored", "reason": "bot_message"}

    message_id = str(message_id_value) if message_id_value else None
    reply_to = message.get("reply_to_message") or {}
    reply_to_message_id = (
        str(reply_to.get("message_id")) if reply_to.get("message_id") is not None else None
    )
    thread_id = (
        message.get("message_thread_id")
        or message.get("reply_to_message", {}).get("message_thread_id")
        or message.get("forum_topic_created", {}).get("message_thread_id")
    )
    if thread_id is not None:
        thread_id = str(thread_id)

    if text:
        command = text.split()[0].lower()
    else:
        command = None

    if command and command.startswith("/getid"):
        if chat_id is None:
            return {"status": "ignored"}
        tg_service = TelegramService(bot_token)
        chat_type = chat.get("type") or "unknown"
        response_lines = [f"Chat ID: {chat_id}", f"Type: {chat_type}"]
        if thread_id:
            response_lines.append(f"Thread ID: {thread_id}")
        print("[getid] responding", chat_id, thread_id)
        try:
            await tg_service.send_message(
                chat_id=chat_id,
                text="\n".join(response_lines),
            )
        except Exception as exc:  # noqa: BLE001
            print("[getid] send error", exc)
            return {"status": "error", "detail": str(exc)}
        return {"status": "ok", "data": {"command": "getid", "chat_id": chat_id, "thread_id": thread_id}}

    if chat_id is None:
        return {"status": "ignored"}

    service = DialogService(session)
    try:
        result = await service.handle_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            telegram_message=message,
            message_id=message_id,
            message_thread_id=thread_id,
            reply_to_message_id=reply_to_message_id,
        )
    except ValueError as exc:
        context = {
            "bot_id": bot_id,
            "chat_id": chat_id,
            "thread_id": thread_id,
            "message_id": message_id,
            "text_preview": (text or "")[:80],
            "reply_to_message_id": reply_to_message_id,
            "payload_keys": sorted(payload.keys()),
            "has_message_thread_id": "message_thread_id" in message,
            "reply_keys": sorted(reply_to.keys()) if isinstance(reply_to, dict) else None,
            "reply_message_thread_id": reply_to.get("message_thread_id") if isinstance(reply_to, dict) else None,
        }
        print("[webhook] dialog resolution error", context)
        return {"status": "ignored", "reason": str(exc), "context": context}
    return {"status": "ok", "data": result}


async def _handle_my_chat_member_update(
    *,
    session: AsyncSession,
    bot,
    update: dict,
) -> dict[str, object]:
    chat_payload = update.get("chat") or {}
    chat_type = chat_payload.get("type")
    if chat_type not in {"group", "supergroup"}:
        return {"ignored": True, "reason": "unsupported_chat_type", "chat_type": chat_type}

    chat_id_value = chat_payload.get("id")
    if chat_id_value is None:
        return {"ignored": True, "reason": "missing_chat_id"}

    chat_id = str(chat_id_value)
    title = chat_payload.get("title") or chat_payload.get("username")
    username = chat_payload.get("username")
    is_forum = chat_payload.get("is_forum")

    new_state = update.get("new_chat_member") or {}
    status = new_state.get("status")

    is_member = status in {"creator", "administrator", "member"}
    if status == "restricted":
        is_member = bool(new_state.get("is_member"))

    repo = TelegramChatRepository(session)
    chat = await repo.upsert_membership(
        bot_id=bot.id,
        chat_id=chat_id,
        title=title,
        chat_type=chat_type,
        username=username,
        is_forum=is_forum,
        status=status,
        is_member=is_member,
    )

    return {
        "chat_id": chat.chat_id,
        "bot_id": bot.id,
        "status": status,
        "is_active": chat.is_active,
    }


@router.post("/avito")
async def avito_webhook(
    request: Request,
    session: AsyncSession = Depends(deps.get_db),
):
    payload = await request.json()
    client_id = payload.get("client_id")
    account_id = payload.get("avito_account_id")
    dialog_id = payload.get("dialog_id")
    message = payload.get("message", {})
    text = message.get("text")
    sender = message.get("sender")
    message_id = message.get("id")
    if not all([client_id, account_id, dialog_id, text]):
        raise HTTPException(status_code=400, detail="Invalid payload")
    service = DialogService(session)
    try:
        result = await service.handle_avito_message(
            client_id=client_id,
            avito_account_id=account_id,
            avito_dialog_id=str(dialog_id),
            message_text=text,
            sender=sender,
            source_message_id=str(message_id) if message_id is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "data": result}
