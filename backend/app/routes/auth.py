from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AdminPasswordLoginRequest,
    BootstrapAdminRequest,
    LoginRequest,
    TelegramLinkExchangeRequest,
    TelegramLinkExchangeResponse,
    TelegramLinkRequest,
    TelegramLinkResponse,
    TelegramAuthRequest,
    TokenResponse,
)
from app.schemas.settings import TelegramConfigResponse
from app.services.auth import AuthService
from app.repositories.project_settings_repository import ProjectSettingsRepository

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    token = await AuthService(session).authenticate(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post("/admin/login", response_model=TokenResponse)
async def admin_password_login(
    payload: AdminPasswordLoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if (
        payload.username != settings.admin_basic_username
        or payload.password != settings.admin_basic_password
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")

    service = AuthService(session)
    admin = await service.bootstrap_admin(
        settings.admin_account_email,
        settings.admin_basic_password,
        settings.admin_account_name,
    )
    token = create_access_token(str(admin.id), extra_claims={"role": admin.role.value})
    return TokenResponse(access_token=token)


@router.post("/telegram", response_model=TokenResponse)
async def login_telegram(payload: TelegramAuthRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    token = await AuthService(session).authenticate_telegram(payload)
    return TokenResponse(access_token=token)


@router.post("/bootstrap-admin", response_model=TokenResponse)
async def bootstrap_admin(payload: BootstrapAdminRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    service = AuthService(session)
    admin = await service.bootstrap_admin(payload.email, payload.password, payload.full_name)
    token = create_access_token(str(admin.id), extra_claims={"role": admin.role.value})
    return TokenResponse(access_token=token)


@router.post("/master/link", response_model=TelegramLinkResponse)
async def create_login_link(payload: TelegramLinkRequest, session: AsyncSession = Depends(get_db)) -> TelegramLinkResponse:
    try:
        role = UserRole(payload.role)
    except ValueError:
        role = UserRole.manager
    service = AuthService(session)
    link_token = await service.issue_telegram_token(payload.telegram_user_id, role)
    return TelegramLinkResponse(link_token=link_token)


@router.post("/master/exchange", response_model=TelegramLinkExchangeResponse)
async def exchange_link(payload: TelegramLinkExchangeRequest, session: AsyncSession = Depends(get_db)) -> TelegramLinkExchangeResponse:
    service = AuthService(session)
    claims = service.validate_link_token(payload.token)
    telegram_user_id = claims["sub"]
    desired_role = UserRole(claims.get("role", "manager"))

    user_repo = UserRepository(session)
    client_repo = ClientRepository(session)

    existing_user = await user_repo.get_by_email(payload.email)
    client_created = False

    if existing_user:
        existing_user.telegram_user_id = telegram_user_id
        if payload.full_name:
            existing_user.full_name = payload.full_name
        await session.commit()
        await session.refresh(existing_user)
        token = create_access_token(str(existing_user.id), extra_claims={"role": existing_user.role.value})
        return TelegramLinkExchangeResponse(access_token=token, client_created=False)

    client_name = payload.full_name or payload.email.split("@")[0]
    client = await client_repo.create(name=client_name)
    client_created = True

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=UserRole.owner if desired_role != UserRole.admin else UserRole.admin,
        telegram_user_id=telegram_user_id,
        client_id=client.id,
    )
    await user_repo.create(user)
    token = create_access_token(str(user.id), extra_claims={"role": user.role.value})
    return TelegramLinkExchangeResponse(access_token=token, client_created=client_created)


@router.post("/master/register", response_model=TelegramLinkExchangeResponse)
async def register_via_master(payload: TelegramAuthRequest, session: AsyncSession = Depends(get_db)) -> TelegramLinkExchangeResponse:
    service = AuthService(session)
    user, created = await service.register_via_master(payload)
    token = create_access_token(str(user.id), extra_claims={"role": user.role.value})
    return TelegramLinkExchangeResponse(access_token=token, client_created=created)


@router.get("/telegram/config", response_model=TelegramConfigResponse)
async def get_telegram_config(session: AsyncSession = Depends(get_db)) -> TelegramConfigResponse:
    repo = ProjectSettingsRepository(session)
    settings = await repo.get()
    bot_name = settings.master_bot_name or None
    if bot_name and bot_name.startswith("@"):
        bot_name = bot_name[1:]
    return TelegramConfigResponse(bot_username=bot_name)
