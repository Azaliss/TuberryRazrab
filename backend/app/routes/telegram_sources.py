from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api import deps
from app.core.config import settings
from app.models.enums import TelegramSourceStatus, UserRole
from app.repositories.bot_repository import BotRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.telegram_source_repository import TelegramSourceRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.telegram_source import (
    TelegramSourceCreateRequest,
    TelegramSourceResponse,
    TelegramSourceUpdateRequest,
)
from app.services.telegram import TelegramService
from app.services.telegram_source import TelegramSourceService

router = APIRouter()


def _build_response(source, service: TelegramSourceService) -> TelegramSourceResponse:
    payload: dict[str, Any] = source.dict()
    payload["webhook_url"] = service.build_webhook_url(source)
    return TelegramSourceResponse.model_validate(payload)


@router.get("", response_model=list[TelegramSourceResponse])
@router.get("/", response_model=list[TelegramSourceResponse], include_in_schema=False)
async def list_telegram_sources(
    project_id: int | None = None,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    service = TelegramSourceService(session)
    if project_id is not None:
        project = await ProjectRepository(session).get(project_id)
        if project is None or project.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
        sources = await service.source_repo.list_for_project(project_id)
    else:
        sources = await service.source_repo.list_for_client(user.client_id)
    return [_build_response(source, service) for source in sources]


@router.post("", response_model=TelegramSourceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TelegramSourceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_telegram_source(
    payload: TelegramSourceCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    project_repo = ProjectRepository(session)
    project = await project_repo.get(payload.project_id)
    if project is None or project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")

    bot_repo = BotRepository(session)
    controller_bot = await bot_repo.get(payload.bot_id)
    if controller_bot is None or controller_bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Управляющий бот не найден")
    if not controller_bot.group_chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Для управляющего бота не настроен рабочий чат")

    if project.bot_id is None or project.bot_id != controller_bot.id:
        try:
            project = await project_repo.update(project, bot_id=controller_bot.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to bind bot %s to project %s: %s", controller_bot.id, project.id, exc)

    if not settings.webhook_base_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_BASE_URL не настроен в конфигурации")

    repo = TelegramSourceRepository(session)
    existing = await repo.get_by_token(payload.token)
    if existing and existing.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот токен уже используется другим клиентом")

    service = TelegramSourceService(session)

    telegram = TelegramService(payload.token)
    try:
        me = await telegram.get_me()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный токен Telegram бота") from exc

    username = me.get("username")
    default_display = me.get("first_name") or me.get("last_name") or username
    display_name = payload.display_name or default_display

    if existing and existing.client_id == user.client_id:
        source = await repo.update(
            existing,
            bot_id=payload.bot_id,
            token=payload.token,
            display_name=display_name,
            description=payload.description,
            bot_username=username,
            project_id=project.id,
        )
    else:
        source = await repo.create(
            client_id=user.client_id,
            project_id=project.id,
            bot_id=payload.bot_id,
            token=payload.token,
            bot_username=username,
            display_name=display_name,
            description=payload.description,
        )

    try:
        await service.ensure_webhook(source)
    except Exception as exc:  # noqa: BLE001
        await repo.update(source, status=TelegramSourceStatus.error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось настроить вебхук Telegram источника") from exc

    source = (await repo.get(source.id)) or source
    return _build_response(source, service)


@router.patch("/{source_id}", response_model=TelegramSourceResponse)
async def update_telegram_source(
    source_id: int,
    payload: TelegramSourceUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = TelegramSourceRepository(session)
    source = await repo.get(source_id)
    if source is None or source.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Источник не найден")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    updates: dict[str, Any] = {}

    project_repo = ProjectRepository(session)
    project = None
    if source.project_id:
        project = await project_repo.get(source.project_id)

    if payload.project_id is not None and payload.project_id != source.project_id:
        project = await project_repo.get(payload.project_id)
        if project is None or project.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
        updates["project_id"] = project.id

    if payload.bot_id is not None and payload.bot_id != source.bot_id:
        bot = await BotRepository(session).get(payload.bot_id)
        if bot is None or bot.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Управляющий бот не найден")
        if not bot.group_chat_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Для управляющего бота не настроен рабочий чат")
        updates["bot_id"] = payload.bot_id
        if project and (project.bot_id is None or project.bot_id != bot.id):
            try:
                await project_repo.update(project, bot_id=bot.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to bind bot %s to project %s: %s", bot.id, project.id, exc)

    if payload.display_name is not None:
        updates["display_name"] = payload.display_name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.status is not None:
        updates["status"] = payload.status

    if updates:
        source = await repo.update(source, **updates)

    service = TelegramSourceService(session)
    if payload.status == TelegramSourceStatus.active:
        try:
            await service.ensure_webhook(source)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось активировать вебхук Telegram источника") from exc

    return _build_response(source, service)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_telegram_source(
    source_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = TelegramSourceRepository(session)
    source = await repo.get(source_id)
    if source is None or source.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Источник не найден")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    service = TelegramSourceService(session)
    try:
        await service.delete_webhook(source, drop_pending_updates=True)
    except Exception:  # noqa: BLE001
        pass

    dialog_repo = DialogRepository(session)
    message_repo = MessageRepository(session)

    dialogs = await dialog_repo.list_for_telegram_source(source.id)
    dialog_ids = [dialog.id for dialog in dialogs]

    if dialog_ids:
        await message_repo.delete_for_dialogs(dialog_ids)
        for dialog in dialogs:
            await dialog_repo.delete(dialog)

    await repo.delete(source)
