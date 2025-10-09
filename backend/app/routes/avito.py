from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.enums import UserRole
from app.repositories.avito_repository import AvitoAccountRepository
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.avito import AvitoAccountCreateRequest, AvitoAccountResponse, AvitoAccountUpdateRequest

router = APIRouter()


@router.get("/accounts", response_model=list[AvitoAccountResponse])
async def list_accounts(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")
    accounts = await AvitoAccountRepository(session).list_for_client(user.client_id)
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
    repo = AvitoAccountRepository(session)
    account = await repo.create(
        client_id=user.client_id,
        api_client_id=payload.api_client_id,
        api_client_secret=payload.api_client_secret,
        name=payload.name,
        access_token=payload.access_token,
        expires_at=payload.token_expires_at,
        bot_id=payload.bot_id,
        monitoring_enabled=payload.monitoring_enabled if payload.monitoring_enabled is not None else True,
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
    account = await repo.update(account, **payload.dict(exclude_unset=True))
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

    await session.flush()
    await session.delete(account)
    await session.commit()
