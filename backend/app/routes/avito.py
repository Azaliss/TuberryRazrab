from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api import deps
from app.models.enums import UserRole
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.bot_repository import BotRepository
from app.schemas.avito import AvitoAccountCreateRequest, AvitoAccountResponse, AvitoAccountUpdateRequest
from app.services.avito import AvitoService

router = APIRouter()


@router.get("/accounts", response_model=list[AvitoAccountResponse])
async def list_accounts(
    project_id: int | None = None,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    repo = AvitoAccountRepository(session)
    if project_id is not None:
        project = await ProjectRepository(session).get(project_id)
        if project is None or project.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        accounts = await repo.list_for_project(project_id)
    else:
        accounts = await repo.list_for_client(user.client_id)
    return accounts


@router.post("/accounts", response_model=AvitoAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AvitoAccountCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    if payload.project_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите проект для интеграции Авито")

    project_repo = ProjectRepository(session)
    project = await project_repo.get(payload.project_id)
    if project is None or project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    bot_repo = BotRepository(session)
    bot_id = payload.bot_id or project.bot_id
    if bot_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Проект не привязан к боту")
    bot = await bot_repo.get(bot_id)
    if bot is None or bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    if project.bot_id is None or project.bot_id != bot.id:
        try:
            project = await project_repo.update(project, bot_id=bot.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to bind bot %s to project %s: %s", bot.id, project.id, exc)

    repo = AvitoAccountRepository(session)
    account = await repo.create(
        client_id=user.client_id,
        project_id=project.id,
        api_client_id=payload.api_client_id,
        api_client_secret=payload.api_client_secret,
        name=payload.name,
        access_token=payload.access_token,
        expires_at=payload.token_expires_at,
        bot_id=bot.id,
        monitoring_enabled=payload.monitoring_enabled if payload.monitoring_enabled is not None else True,
    )
    service = AvitoService()
    try:
        await service.ensure_webhook_for_account(account, repo)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to register Avito webhook after account creation",
            account_id=account.id,
            error=str(exc),
        )
    return account


@router.patch("/accounts/{account_id}", response_model=AvitoAccountResponse)
async def update_account(
    account_id: int,
    payload: AvitoAccountUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = AvitoAccountRepository(session)
    account = await repo.get(account_id)
    if account is None or account.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    updates = payload.dict(exclude_unset=True)

    project_repo = ProjectRepository(session)
    bot_repo = BotRepository(session)

    target_project_id = updates.get("project_id", account.project_id)
    project = None
    if target_project_id is not None:
        project = await project_repo.get(target_project_id)
        if project is None or project.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    elif account.project_id:
        project = await project_repo.get(account.project_id)

    target_bot_id = updates.get("bot_id")
    if target_bot_id is None:
        if project and project.bot_id:
            target_bot_id = project.bot_id
        else:
            target_bot_id = account.bot_id

    if target_bot_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Проект не привязан к боту")

    bot = await bot_repo.get(target_bot_id)
    if bot is None or bot.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    if project and (project.bot_id is None or project.bot_id != bot.id):
        try:
            project = await project_repo.update(project, bot_id=bot.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to bind bot %s to project %s: %s", bot.id, project.id, exc)

    updates["bot_id"] = bot.id
    updates["project_id"] = project.id if project is not None else None

    account = await repo.update(account, **updates)
    service = AvitoService()
    try:
        await service.ensure_webhook_for_account(account, repo)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to register Avito webhook after account update",
            account_id=account.id,
            error=str(exc),
        )
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = AvitoAccountRepository(session)
    account = await repo.get(account_id)
    if account is None or account.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    dialog_repo = DialogRepository(session)
    message_repo = MessageRepository(session)

    dialogs = await dialog_repo.list_for_avito_account(account.id)
    dialog_ids = [dialog.id for dialog in dialogs]

    if dialog_ids:
        await message_repo.delete_for_dialogs(dialog_ids)
        for dialog in dialogs:
            await dialog_repo.delete(dialog)

    service = AvitoService()
    try:
        await service.disable_webhook_for_account(account, repo)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to disable Avito webhook before account deletion",
            account_id=account.id,
            error=str(exc),
        )

    await session.flush()
    await session.delete(account)
    await session.commit()
