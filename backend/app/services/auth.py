import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.project_settings_repository import ProjectSettingsRepository
from app.schemas.auth import TelegramAuthRequest


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.settings_repo = ProjectSettingsRepository(session)

    async def authenticate(self, email: str, password: str) -> str:
        self._ensure_password_length(password)
        user = await self.user_repo.get_by_email(email)
        client_repo = ClientRepository(self.session)

        if user is None:
            client = await client_repo.create(name=self._derive_client_name(email))
            new_user = User(
                email=email,
                role=UserRole.owner,
                client_id=client.id,
            )
            user = await self.user_repo.create(new_user, password=password)
        else:
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

            if user.hashed_password is None:
                user.hashed_password = get_password_hash(password)
                if user.client_id is None:
                    client = await client_repo.create(name=self._derive_client_name(email))
                    user.client_id = client.id
                await self.session.commit()
                await self.session.refresh(user)

            try:
                if not verify_password(password, user.hashed_password):
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            except ValueError as exc:
                if "password cannot be longer than 72 bytes" in str(exc):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Пароль слишком длинный. Максимум 72 символа",
                    ) from exc
                raise

        return create_access_token(str(user.id), extra_claims={"role": user.role.value})

    @staticmethod
    def _derive_client_name(login: str) -> str:
        base = login.split("@")[0] if "@" in login else login
        base = base or "Client"
        return base[:64]

    async def bootstrap_admin(self, email: str, password: str, full_name: Optional[str] = None) -> User:
        self._ensure_password_length(password)
        existing = await self.user_repo.get_by_email(email)
        if existing:
            if password:
                existing.hashed_password = get_password_hash(password)
            if full_name and not existing.full_name:
                existing.full_name = full_name
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        return await self.user_repo.create_admin(email=email, password=password, full_name=full_name)

    async def issue_telegram_token(self, telegram_user_id: str, role: UserRole = UserRole.manager) -> str:
        expires = timedelta(minutes=30)
        return create_access_token(telegram_user_id, int(expires.total_seconds()), {"kind": "tg_link", "role": role.value})

    def validate_link_token(self, token: str) -> dict:
        try:
            payload = self._decode(token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if payload.get("kind") != "tg_link":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token kind")
        if "sub" not in payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subject")
        return payload

    async def authenticate_telegram(self, payload: TelegramAuthRequest) -> str:
        project_settings = await self.settings_repo.get()
        master_bot_token = project_settings.master_bot_token
        if not master_bot_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram auth is not configured")

        self._verify_telegram_payload(payload, master_bot_token)

        telegram_user_id = str(payload.id)
        user = await self.user_repo.get_by_telegram_user_id(telegram_user_id)
        client_repo = ClientRepository(self.session)

        if not user:
            full_name_parts = [part for part in [payload.first_name, payload.last_name] if part]
            derived_full_name = " ".join(full_name_parts) if full_name_parts else None
            default_client_name = derived_full_name or payload.username or f"Telegram {telegram_user_id}"

            client = await client_repo.create(name=default_client_name)

            generated_password = f"{telegram_user_id}tuberry1"
            user = await self.user_repo.create(
                User(
                    email=telegram_user_id,
                    full_name=derived_full_name,
                    role=UserRole.owner,
                    telegram_user_id=telegram_user_id,
                    client_id=client.id,
                ),
                password=generated_password,
            )
        else:
            updated = False
            if not user.hashed_password:
                user.hashed_password = get_password_hash(f"{telegram_user_id}tuberry1")
                updated = True
            if not user.email:
                user.email = telegram_user_id
                updated = True
            if not user.client_id:
                client = await client_repo.create(name=self._derive_client_name(telegram_user_id))
                user.client_id = client.id
                updated = True
            full_name_parts = [part for part in [payload.first_name, payload.last_name] if part]
            derived_full_name = " ".join(full_name_parts)
            if derived_full_name and not user.full_name:
                user.full_name = derived_full_name
                updated = True
            if updated:
                await self.session.commit()
                await self.session.refresh(user)

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован")

        return create_access_token(str(user.id), extra_claims={"role": user.role.value})

    async def register_via_master(self, payload: TelegramAuthRequest) -> tuple[User, bool]:
        project_settings = await self.settings_repo.get()
        master_bot_token = project_settings.master_bot_token
        if not master_bot_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram auth is not configured")

        self._verify_telegram_payload(payload, master_bot_token)

        telegram_user_id = str(payload.id)
        existing_user = await self.user_repo.get_by_telegram_user_id(telegram_user_id)
        if existing_user:
            return existing_user, False

        full_name_parts = [part for part in [payload.first_name, payload.last_name] if part]
        full_name = " ".join(full_name_parts) if full_name_parts else None
        default_client_name = full_name or payload.username or f"Telegram {telegram_user_id}"

        client_repo = ClientRepository(self.session)
        client = await client_repo.create(name=default_client_name)

        user = User(
            email=(payload.username and f"{payload.username}@telegram.local") or None,
            full_name=full_name,
            role=UserRole.owner,
            telegram_user_id=telegram_user_id,
            client_id=client.id,
        )
        created_user = await self.user_repo.create(user)
        return created_user, True

    def _verify_telegram_payload(self, payload: TelegramAuthRequest, master_bot_token: str) -> None:
        secret_key = hashlib.sha256(master_bot_token.encode()).digest()
        data = payload.model_dump(exclude_none=True, exclude={"hash"})
        data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, payload.hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительная подпись Telegram")

        auth_datetime = datetime.fromtimestamp(payload.auth_date, tz=timezone.utc)
        if datetime.now(timezone.utc) - auth_datetime > timedelta(minutes=5):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия Telegram устарела")

    @staticmethod
    def _decode(token: str) -> dict:
        from app.core.security import decode_access_token

        try:
            return decode_access_token(token)
        except (ValueError, JWTError):
            raise ValueError("Invalid token")

    @staticmethod
    def hash_password(raw: str) -> str:
        return get_password_hash(raw)

    @staticmethod
    def _ensure_password_length(password: str) -> None:
        if len(password.encode("utf-8")) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пароль слишком длинный. Максимум 72 символа",
            )
