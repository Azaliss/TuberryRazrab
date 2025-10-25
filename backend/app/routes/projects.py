from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.config import settings
from app.models.enums import AutoReplyMode, BotStatus, UserRole
from app.models.telegram_chat import TelegramChat
from app.repositories.bot_repository import BotRepository
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.telegram_source_repository import TelegramSourceRepository
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.telegram import TelegramService
from app.services.telegram_source import TelegramSourceService

router = APIRouter()

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    base = value.strip().lower()
    if not base:
        base = "project"
    slug = re.sub(r"[^a-z0-9\-_.]+", "-", base)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


async def _ensure_unique_slug(repo: ProjectRepository, client_id: int, slug: str, *, exclude_project_id: int | None = None) -> str:
    candidate = slug
    suffix = 2
    while True:
        existing = await repo.get_by_slug(client_id, candidate)
        if existing is None or (exclude_project_id is not None and existing.id == exclude_project_id):
            return candidate
        candidate = f"{slug}-{suffix}"
        suffix += 1


async def _validate_bot_binding(
    *,
    repo: ProjectRepository,
    bot_repo: BotRepository,
    client_id: int,
    bot_id: int | None,
    project_id: int | None,
) -> int | None:
    if bot_id is None:
        return None
    bot = await bot_repo.get(bot_id)
    if bot is None or bot.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    existing = await repo.get_by_bot_id(bot_id)
    if existing and existing.id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот бот уже привязан к другому проекту")
    return bot.id


def _prepare_auto_reply_payload(*, payload: dict[str, Any], existing: Any | None = None) -> dict[str, Any]:
    def _get(field: str, default: Any) -> Any:
        if field in payload and payload[field] is not None:
            return payload[field]
        if existing is not None:
            return getattr(existing, field)
        return default

    text_raw = payload.get("auto_reply_text")
    timezone_raw = payload.get("auto_reply_timezone")
    if text_raw is not None and isinstance(text_raw, str):
        payload["auto_reply_text"] = text_raw.strip() or None
    if timezone_raw is not None and isinstance(timezone_raw, str):
        payload["auto_reply_timezone"] = timezone_raw.strip() or None

    enabled = _get("auto_reply_enabled", False)
    always = _get("auto_reply_always", False)
    start_time = _get("auto_reply_start_time", None)
    end_time = _get("auto_reply_end_time", None)
    timezone = _get("auto_reply_timezone", None)
    text = _get("auto_reply_text", None)

    mode_value = payload.get("auto_reply_mode")
    if mode_value is not None and not isinstance(mode_value, AutoReplyMode):
        try:
            mode_value = AutoReplyMode(mode_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимый режим автоответа") from exc
    elif mode_value is None:
        mode_value = existing.auto_reply_mode if existing is not None else AutoReplyMode.always

    if timezone:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Указан неверный часовой пояс") from exc
    elif enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите часовой пояс для автоответа")

    if enabled:
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите текст автоответа")
        if not always:
            if start_time is None or end_time is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите время начала и окончания автоответа")
            if start_time == end_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Время начала и окончания не могут совпадать")

    return {
        "auto_reply_enabled": bool(enabled),
        "auto_reply_always": bool(always),
        "auto_reply_start_time": start_time,
        "auto_reply_end_time": end_time,
        "auto_reply_timezone": timezone,
        "auto_reply_text": text,
        "auto_reply_mode": mode_value,
    }


async def _create_bot_from_token(
    *,
    bot_repo: BotRepository,
    client_id: int,
    token: str,
    topic_mode: bool | None,
    group_chat_id: str | None,
) -> tuple[Any, TelegramService]:
    clean_token = token.strip()
    tg_service = TelegramService(clean_token)
    try:
        me = await tg_service.get_me()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch Telegram bot profile via getMe")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось получить данные Telegram-бота. Проверьте токен.") from exc

    bot_username = me.get("username")
    resolved_topic_mode = True if topic_mode is None else bool(topic_mode)

    bot = await bot_repo.create(
        client_id=client_id,
        token=clean_token,
        bot_username=bot_username,
        group_chat_id=None,
        topic_mode=resolved_topic_mode,
    )

    updates: dict[str, Any] = {"bot_username": bot_username, "topic_mode": resolved_topic_mode}

    webhook_base = settings.webhook_base_url.rstrip("/") if settings.webhook_base_url else None
    if not webhook_base:
        await bot_repo.delete(bot)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_BASE_URL не настроен. Укажите публичный адрес в конфигурации.")

    if group_chat_id:
        stripped_chat_id = group_chat_id.strip()
        try:
            chat_details = await tg_service.get_chat(stripped_chat_id)
        except Exception as exc:  # noqa: BLE001
            await bot_repo.delete(bot)
            logger.exception("Failed to fetch Telegram chat info for bot")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось получить чат Telegram. Убедитесь, что бот добавлен в группу и указан корректный ID.") from exc
        updates["group_chat_id"] = str(chat_details.get("id", stripped_chat_id))
        updates["status"] = BotStatus.active
    else:
        updates["status"] = BotStatus.inactive

    webhook_url = f"{webhook_base}/api/webhooks/telegram/{bot.id}/{bot.webhook_secret}"
    try:
        await tg_service.set_webhook(
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
        await bot_repo.delete(bot)
        logger.exception("Failed to configure Telegram webhook for bot")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось настроить вебхук Telegram бота. Проверьте доступность публичного адреса.") from exc

    bot = await bot_repo.update(bot, **updates)
    return bot, tg_service


async def _ensure_bot_as_source(
    *,
    session: AsyncSession,
    project,
    bot,
    client_id: int,
    token: str,
) -> None:
    source_repo = TelegramSourceRepository(session)
    source_service = TelegramSourceService(session)
    existing_source = await source_repo.get_by_token(token)

    if existing_source:
        if existing_source.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот бот уже используется другим клиентом как источник")
        updates: dict[str, Any] = {}
        if existing_source.bot_id != bot.id:
            updates["bot_id"] = bot.id
        if existing_source.project_id != project.id:
            updates["project_id"] = project.id
        source = await source_repo.update(existing_source, **updates) if updates else existing_source
    else:
        display_name = bot.bot_username or f"Bot {bot.id}"
        source = await source_repo.create(
            client_id=client_id,
            project_id=project.id,
            bot_id=bot.id,
            token=token,
            bot_username=bot.bot_username,
            display_name=display_name,
            description=None,
        )

    try:
        await source_service.ensure_webhook(source)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to configure Telegram source webhook")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось настроить вебхук Telegram источника") from exc


async def _cleanup_and_delete_bot(session: AsyncSession, bot) -> None:
    dialog_repo = DialogRepository(session)
    message_repo = MessageRepository(session)
    avito_repo = AvitoAccountRepository(session)

    tg_service = TelegramService(bot.token)
    try:
        await tg_service.delete_webhook(drop_pending_updates=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete Telegram webhook for bot %s: %s", bot.id, exc)

    dialogs = await dialog_repo.list_for_bot(bot.id)
    dialog_ids = [dialog.id for dialog in dialogs]
    if dialog_ids:
        await message_repo.delete_for_dialogs(dialog_ids)
        for dialog in dialogs:
            await dialog_repo.delete(dialog)

    accounts = await avito_repo.list_by_bot(bot.id)
    for account in accounts:
        account.bot_id = None
        account.updated_at = datetime.utcnow()

    await session.flush()
    await session.execute(delete(TelegramChat).where(TelegramChat.bot_id == bot.id))
    await session.delete(bot)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    projects = await ProjectRepository(session).list_for_client(user.client_id)
    return projects


@router.get("", response_model=list[ProjectResponse], include_in_schema=False)
async def list_projects_no_slash(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    return await list_projects(session=session, user=user)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = ProjectRepository(session)
    project = await repo.get(project_id)
    if project is None or project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return project


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")

    repo = ProjectRepository(session)
    bot_repo = BotRepository(session)

    slug_source = payload.slug or _slugify(payload.name)
    slug = await _ensure_unique_slug(repo, user.client_id, slug_source)
    raw_bot_token = (payload.bot_token or "").strip()
    group_chat_id = payload.bot_group_chat_id.strip() if payload.bot_group_chat_id else None
    bot_topic_mode = payload.bot_topic_mode
    bot = None

    if raw_bot_token:
        existing_bot = await bot_repo.get_by_token(raw_bot_token)
        if existing_bot:
            if existing_bot.client_id != user.client_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот бот уже привязан другому клиенту")
            await _validate_bot_binding(
                repo=repo,
                bot_repo=bot_repo,
                client_id=user.client_id,
                bot_id=existing_bot.id,
                project_id=None,
            )
            updates: dict[str, Any] = {}
            if bot_topic_mode is not None and bool(bot_topic_mode) != existing_bot.topic_mode:
                updates["topic_mode"] = bool(bot_topic_mode)
            if group_chat_id and group_chat_id != existing_bot.group_chat_id:
                tg_service = TelegramService(raw_bot_token)
                try:
                    chat_details = await tg_service.get_chat(group_chat_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to fetch Telegram chat info for existing bot")
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось получить чат Telegram. Проверьте корректность ID и наличие бота в группе.") from exc
                updates["group_chat_id"] = str(chat_details.get("id", group_chat_id))
                updates["status"] = BotStatus.active
            if updates:
                existing_bot = await bot_repo.update(existing_bot, **updates)
            bot = existing_bot
        else:
            bot, _ = await _create_bot_from_token(
                bot_repo=bot_repo,
                client_id=user.client_id,
                token=raw_bot_token,
                topic_mode=bot_topic_mode,
                group_chat_id=group_chat_id,
            )
        bot_id = bot.id
    else:
        bot_id = await _validate_bot_binding(
            repo=repo,
            bot_repo=bot_repo,
            client_id=user.client_id,
            bot_id=payload.bot_id,
            project_id=None,
        )
        bot = await bot_repo.get(bot_id) if bot_id else None

    auto_reply_payload = _prepare_auto_reply_payload(payload=payload.model_dump(exclude_unset=True), existing=None)

    common_defaults = {
        "status": payload.status or "active",
        "filter_keywords": payload.filter_keywords.strip() if payload.filter_keywords else None,
        "require_reply_for_sources": bool(payload.require_reply_for_sources) if payload.require_reply_for_sources is not None else False,
        "hide_system_messages": bool(payload.hide_system_messages) if payload.hide_system_messages is not None else True,
        "description": payload.description.strip() if payload.description else None,
    }

    topic_intro = payload.topic_intro_template.strip() if payload.topic_intro_template else None

    selected_group_chat_id = group_chat_id or (bot.group_chat_id if bot else None)
    if bot and not selected_group_chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите рабочую группу, куда бот будет создавать топики")

    project = await repo.create(
        client_id=user.client_id,
        name=payload.name,
        slug=slug,
        description=common_defaults["description"],
        status=common_defaults["status"],
        bot_id=bot_id,
        filter_keywords=common_defaults["filter_keywords"],
        require_reply_for_sources=common_defaults["require_reply_for_sources"],
        hide_system_messages=common_defaults["hide_system_messages"],
        auto_reply_enabled=auto_reply_payload["auto_reply_enabled"],
        auto_reply_mode=auto_reply_payload["auto_reply_mode"],
        auto_reply_always=auto_reply_payload["auto_reply_always"],
        auto_reply_start_time=auto_reply_payload["auto_reply_start_time"],
        auto_reply_end_time=auto_reply_payload["auto_reply_end_time"],
        auto_reply_timezone=auto_reply_payload["auto_reply_timezone"],
        auto_reply_text=auto_reply_payload["auto_reply_text"],
        topic_intro_template=topic_intro,
    )

    if payload.use_bot_as_source and bot is not None:
        await _ensure_bot_as_source(
            session=session,
            project=project,
            bot=bot,
            client_id=user.client_id,
            token=bot.token,
    )
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_project_no_slash(
    payload: ProjectCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    return await create_project(payload=payload, session=session, user=user)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = ProjectRepository(session)
    project = await repo.get(project_id)
    if project is None or project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    updates = payload.model_dump(exclude_unset=True)
    previous_auto_reply_enabled = project.auto_reply_enabled

    bot_repo = BotRepository(session)

    raw_bot_token = (updates.pop("bot_token", None) or "").strip() if "bot_token" in updates else ""
    bot_group_chat_id = updates.pop("bot_group_chat_id", None)
    if bot_group_chat_id:
        bot_group_chat_id = bot_group_chat_id.strip()
    bot_topic_mode = updates.pop("bot_topic_mode", None)
    use_bot_as_source = updates.pop("use_bot_as_source", None)

    bot = None

    if raw_bot_token:
        existing_bot = await bot_repo.get_by_token(raw_bot_token)
        if existing_bot:
            if existing_bot.client_id != user.client_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот бот уже привязан другому клиенту")
            await _validate_bot_binding(
                repo=repo,
                bot_repo=bot_repo,
                client_id=user.client_id,
                bot_id=existing_bot.id,
                project_id=project.id,
            )
            updates_for_bot: dict[str, Any] = {}
            if bot_topic_mode is not None and bool(bot_topic_mode) != existing_bot.topic_mode:
                updates_for_bot["topic_mode"] = bool(bot_topic_mode)
            if bot_group_chat_id and bot_group_chat_id != existing_bot.group_chat_id:
                tg_service = TelegramService(raw_bot_token)
                try:
                    chat_details = await tg_service.get_chat(bot_group_chat_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to fetch Telegram chat info for existing bot during update")
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось получить чат Telegram. Проверьте корректность ID и наличие бота в группе.") from exc
                updates_for_bot["group_chat_id"] = str(chat_details.get("id", bot_group_chat_id))
                updates_for_bot["status"] = BotStatus.active
            if updates_for_bot:
                existing_bot = await bot_repo.update(existing_bot, **updates_for_bot)
            bot = existing_bot
        else:
            bot, _ = await _create_bot_from_token(
                bot_repo=bot_repo,
                client_id=user.client_id,
                token=raw_bot_token,
                topic_mode=bot_topic_mode,
                group_chat_id=bot_group_chat_id,
            )
        updates["bot_id"] = bot.id
    elif "bot_id" in updates and updates["bot_id"] is not None:
        updates["bot_id"] = await _validate_bot_binding(
            repo=repo,
            bot_repo=bot_repo,
            client_id=project.client_id,
            bot_id=updates["bot_id"],
            project_id=project.id,
        )
        bot = await bot_repo.get(updates["bot_id"])
    else:
        bot = await bot_repo.get(project.bot_id) if project.bot_id else None
        if bot_topic_mode is not None and bot is not None:
            bot = await bot_repo.update(bot, topic_mode=bool(bot_topic_mode))
        if bot_group_chat_id and bot is not None:
            bot = await bot_repo.update(bot, group_chat_id=bot_group_chat_id)

    if "name" in updates and updates["name"]:
        updates["name"] = updates["name"].strip()

    if updates.get("slug") or updates.get("name"):
        slug_input = updates.get("slug") or _slugify(updates.get("name") or project.name)
        updates["slug"] = await _ensure_unique_slug(repo, project.client_id, slug_input, exclude_project_id=project.id)

    if "bot_id" in updates:
        bot_repo = BotRepository(session)
        validated = await _validate_bot_binding(
            repo=repo,
            bot_repo=bot_repo,
            client_id=project.client_id,
            bot_id=updates["bot_id"],
            project_id=project.id,
        )
        updates["bot_id"] = validated

    auto_reply_payload = _prepare_auto_reply_payload(payload=updates, existing=project)

    for key, value in auto_reply_payload.items():
        updates[key] = value

    if "filter_keywords" in updates and updates["filter_keywords"] is not None:
        updates["filter_keywords"] = updates["filter_keywords"].strip() or None

    if "description" in updates and updates["description"] is not None:
        updates["description"] = updates["description"].strip() or None

    if "topic_intro_template" in updates:
        value = updates.get("topic_intro_template")
        if value is None:
            updates["topic_intro_template"] = None
        else:
            updates["topic_intro_template"] = value.strip() or None

    selected_group_chat_id = bot_group_chat_id or (bot.group_chat_id if bot else None)
    if bot and not selected_group_chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите рабочую группу, куда бот будет создавать топики")

    project = await repo.update(project, **updates)

    if project.auto_reply_enabled and not previous_auto_reply_enabled:
        await DialogRepository(session).reset_auto_reply_marks_for_project(project.id)

    if use_bot_as_source and bot is not None:
        await _ensure_bot_as_source(
            session=session,
            project=project,
            bot=bot,
            client_id=project.client_id,
            token=bot.token,
        )

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = ProjectRepository(session)
    project = await repo.get(project_id)
    if project is None or project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    avito_repo = AvitoAccountRepository(session)
    telegram_repo = TelegramSourceRepository(session)
    linked_accounts = await avito_repo.list_for_project(project.id)
    linked_sources = await telegram_repo.list_for_project(project.id)

    if linked_accounts or linked_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Удалите подключённые источники (Avito и Telegram) перед удалением проекта",
        )

    bot_id = project.bot_id

    await repo.delete(project)

    if bot_id:
        bot_repo = BotRepository(session)
        bot = await bot_repo.get(bot_id)
        if bot is not None:
            await _cleanup_and_delete_bot(session, bot)
            await session.commit()
    return None
