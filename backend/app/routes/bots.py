from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.config import settings
from app.models.enums import BotStatus, UserRole
from app.models.telegram_chat import TelegramChat
from app.repositories.bot_repository import BotRepository
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.telegram_chat_repository import TelegramChatRepository
from app.schemas.bot import BotCreateRequest, BotResponse, BotUpdateRequest
from app.schemas.telegram_chat import TelegramChatResponse
from app.services.telegram import TelegramService

router = APIRouter()


@router.get("/", response_model=list[BotResponse])
async def list_bots(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    bots = await BotRepository(session).list_for_client(user.client_id)
    return bots


@router.post("/", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    payload: BotCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    repo = BotRepository(session)
    existing = await repo.get_by_token(payload.token)
    if existing and existing.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот токен уже используется другим клиентом")

    bot = existing or await repo.create(
        client_id=user.client_id,
        token=payload.token,
        bot_username=payload.bot_username,
        group_chat_id=payload.group_chat_id,
        topic_mode=payload.topic_mode,
    )

    service = TelegramService(bot.token)
    updates: dict[str, object] = {"topic_mode": payload.topic_mode}
    try:
        me = await service.get_me()
        username = me.get("username")
        if username:
            updates["bot_username"] = username
    except Exception as exc:  # noqa: BLE001
        if not existing:
            await repo.delete(bot)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный токен бота") from exc

    if payload.group_chat_id:
        try:
            chat = await service.get_chat(payload.group_chat_id)
            updates["group_chat_id"] = str(chat.get("id", payload.group_chat_id))
            updates["status"] = BotStatus.active
        except Exception as exc:  # noqa: BLE001
            if not existing:
                await repo.delete(bot)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный ID группы") from exc
    elif bot.group_chat_id:
        updates["status"] = BotStatus.active
    else:
        updates["status"] = BotStatus.inactive

    bot = await repo.update(bot, **updates)

    if not bot.webhook_secret:
        bot = await repo.update(bot, webhook_secret=None)
    webhook_url = (
        f"{settings.webhook_base_url.rstrip('/')}/api/webhooks/telegram/{bot.id}/"
        f"{bot.webhook_secret}"
    )
    try:
        await service.set_webhook(
            webhook_url,
            secret_token=bot.webhook_secret,
            allowed_updates=[
                "message",
                "edited_message",
                "channel_post",
                "edited_channel_post",
                "callback_query",
                "chat_member",
                "my_chat_member",
                "chat_join_request",
            ],
            drop_pending_updates=True,
        )
    except Exception as exc:  # noqa: BLE001
        if not existing:
            await repo.delete(bot)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось настроить вебхук Telegram") from exc

    return bot


@router.get("/{bot_id}/chats", response_model=list[TelegramChatResponse])
async def list_bot_chats(
    bot_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")

    repo = BotRepository(session)
    bot = await repo.get(bot_id)
    if bot is None or bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    chat_repo = TelegramChatRepository(session)
    chats = await chat_repo.list_active_for_bot(bot_id)

    missing_metadata = [chat for chat in chats if not chat.title]
    if missing_metadata or (bot.group_chat_id and not any(chat.chat_id == bot.group_chat_id for chat in chats)):
        service = TelegramService(bot.token)
        targets = {chat.chat_id: chat for chat in chats}
        if bot.group_chat_id and bot.group_chat_id not in targets:
            targets[bot.group_chat_id] = None
        for chat_id, chat in targets.items():
            if chat is not None and chat.title:
                continue
            try:
                info = await service.get_chat(chat_id)
            except Exception:  # noqa: BLE001
                continue
            title = info.get("title") or info.get("username")
            username = info.get("username")
            is_forum = info.get("is_forum")
            chat_type = info.get("type")
            if chat is None:
                await chat_repo.upsert_membership(
                    bot_id=bot.id,
                    chat_id=str(chat_id),
                    title=title,
                    chat_type=chat_type,
                    username=username,
                    is_forum=is_forum,
                    status="unknown",
                    is_member=True,
                )
            else:
                await chat_repo.update_chat(
                    chat,
                    title=title,
                    username=username,
                    is_forum=is_forum,
                    chat_type=chat_type,
                )

        chats = await chat_repo.list_active_for_bot(bot_id)

    return chats


@router.patch("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: int,
    payload: BotUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = BotRepository(session)
    bot = await repo.get(bot_id)
    if bot is None or bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    bot = await repo.update(bot, **payload.dict(exclude_unset=True))
    return bot


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = BotRepository(session)
    bot = await repo.get(bot_id)
    if bot is None or bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    dialog_repo = DialogRepository(session)
    message_repo = MessageRepository(session)
    avito_repo = AvitoAccountRepository(session)

    service = TelegramService(bot.token)
    try:
        await service.delete_webhook(drop_pending_updates=True)
    except Exception:  # noqa: BLE001
        pass

    dialogs = await dialog_repo.list_for_bot(bot.id)
    dialog_ids = [dialog.id for dialog in dialogs]

    if dialog_ids:
        await message_repo.delete_for_dialogs(dialog_ids)
        for dialog in dialogs:
            await dialog_repo.delete(dialog)

    linked_accounts = await avito_repo.list_by_bot(bot.id)
    for account in linked_accounts:
        account.bot_id = None
        account.updated_at = datetime.utcnow()

    await session.flush()
    await session.execute(delete(TelegramChat).where(TelegramChat.bot_id == bot.id))
    await session.delete(bot)
    await session.commit()
