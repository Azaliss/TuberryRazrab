from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.avito import AvitoAccount
from app.models.bot import Bot
from app.models.client import Client
from app.models.dialog import Dialog
from app.models.user import User
from app.repositories.project_settings_repository import ProjectSettingsRepository
from app.schemas.settings import ProjectSettingsResponse, ProjectSettingsUpdateRequest

router = APIRouter()


@router.get("/summary")
async def summary(
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    counts = {}
    counts["clients"] = (await session.execute(select(func.count(Client.id)))).scalar()
    counts["users"] = (await session.execute(select(func.count(User.id)))).scalar()
    counts["bots"] = (await session.execute(select(func.count(Bot.id)))).scalar()
    counts["avito_accounts"] = (await session.execute(select(func.count(AvitoAccount.id)))).scalar()
    counts["dialogs"] = (await session.execute(select(func.count(Dialog.id)))).scalar()
    return counts


@router.get("/settings", response_model=ProjectSettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    repo = ProjectSettingsRepository(session)
    settings = await repo.get()
    return settings


@router.put("/settings", response_model=ProjectSettingsResponse)
async def update_settings(
    payload: ProjectSettingsUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    repo = ProjectSettingsRepository(session)
    settings = await repo.get()
    updated = await repo.update(settings, **payload.model_dump(exclude_unset=True))
    return updated
