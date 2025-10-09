from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_telegram_user_id(self, telegram_user_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
        return result.scalar_one_or_none()

    async def create_admin(self, email: str, password: str, full_name: str | None = None) -> User:
        admin = User(email=email, full_name=full_name, role=UserRole.admin, hashed_password=get_password_hash(password))
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def create(self, user: User, password: str | None = None) -> User:
        if password:
            user.hashed_password = get_password_hash(password)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
