from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.enums import UserRole
from app.schemas.personal_telegram_account import (
    PersonalTelegramAccountLoginRequest,
    PersonalTelegramAccountLoginResponse,
    PersonalTelegramAccountLoginStatusResponse,
    PersonalTelegramAccountPasswordRequest,
    PersonalTelegramAccountResponse,
    PersonalTelegramAccountUpdateRequest,
)
from app.services.personal_telegram_account import PersonalTelegramAccountService

router = APIRouter()


def _ensure_owner(user) -> None:
    if user.role not in (UserRole.owner, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")


@router.get("", response_model=list[PersonalTelegramAccountResponse])
@router.get("/", response_model=list[PersonalTelegramAccountResponse], include_in_schema=False)
async def list_personal_accounts(
    project_id: int | None = None,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    service = PersonalTelegramAccountService(session)
    accounts = await service.list_accounts(client_id=user.client_id, project_id=project_id)
    return [PersonalTelegramAccountResponse.model_validate(account) for account in accounts]


@router.post(
    "/login",
    response_model=PersonalTelegramAccountLoginResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_personal_account_login(
    payload: PersonalTelegramAccountLoginRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    _ensure_owner(user)
    service = PersonalTelegramAccountService(session)
    login_session = await service.start_login(project_id=payload.project_id, client_id=user.client_id)
    return PersonalTelegramAccountLoginResponse(
        login_id=login_session.login_id,
        qr_url=login_session.qr_url,
        expires_at=login_session.expires_at,
    )


@router.get("/login/{login_id}", response_model=PersonalTelegramAccountLoginStatusResponse)
async def get_personal_account_login_status(
    login_id: str = Path(..., min_length=16, description="Идентификатор login-сессии"),
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    service = PersonalTelegramAccountService(session)
    login_session = await service.get_login_session(login_id=login_id, client_id=user.client_id)

    account_payload = None
    if login_session.status == "completed" and login_session.account_id:
        account = await service.account_repo.get(login_session.account_id)
        if account:
            account_payload = PersonalTelegramAccountResponse.model_validate(account)
    return PersonalTelegramAccountLoginStatusResponse(
        status=login_session.status,
        account=account_payload,
        error=login_session.error,
    )


@router.post("/login/{login_id}/password", response_model=PersonalTelegramAccountLoginStatusResponse)
async def submit_personal_account_password(
    payload: PersonalTelegramAccountPasswordRequest,
    login_id: str = Path(..., min_length=16, description="Идентификатор login-сессии"),
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    _ensure_owner(user)
    service = PersonalTelegramAccountService(session)
    login_session = await service.submit_password(login_id=login_id, client_id=user.client_id, password=payload.password)

    account_payload = None
    if login_session.status == "completed" and login_session.account_id:
        account = await service.account_repo.get(login_session.account_id)
        if account:
            account_payload = PersonalTelegramAccountResponse.model_validate(account)

    return PersonalTelegramAccountLoginStatusResponse(
        status=login_session.status,
        account=account_payload,
        error=login_session.error,
    )


@router.patch("/{account_id}", response_model=PersonalTelegramAccountResponse)
async def update_personal_account(
    account_id: int,
    payload: PersonalTelegramAccountUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    _ensure_owner(user)
    service = PersonalTelegramAccountService(session)
    account = await service.get_account(account_id=account_id, client_id=user.client_id)
    updated = await service.update_account(
        account=account,
        display_name=payload.display_name,
        accepts_private=payload.accepts_private,
        accepts_groups=payload.accepts_groups,
        accepts_channels=payload.accepts_channels,
    )
    return PersonalTelegramAccountResponse.model_validate(updated)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_personal_account(
    account_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не привязан к клиенту")
    _ensure_owner(user)
    service = PersonalTelegramAccountService(session)
    account = await service.get_account(account_id=account_id, client_id=user.client_id)
    await service.delete_account(account=account)
    return None
