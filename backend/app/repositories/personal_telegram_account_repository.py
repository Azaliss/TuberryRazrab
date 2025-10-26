from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personal_telegram_account import PersonalTelegramAccount
from app.models.enums import PersonalTelegramAccountStatus


class PersonalTelegramAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, account_id: int) -> PersonalTelegramAccount | None:
        result = await self.session.execute(
            select(PersonalTelegramAccount).where(PersonalTelegramAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def list_for_client(self, client_id: int) -> list[PersonalTelegramAccount]:
        result = await self.session.execute(
            select(PersonalTelegramAccount)
            .where(PersonalTelegramAccount.client_id == client_id)
            .order_by(PersonalTelegramAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_project(self, project_id: int) -> list[PersonalTelegramAccount]:
        result = await self.session.execute(
            select(PersonalTelegramAccount)
            .where(PersonalTelegramAccount.project_id == project_id)
            .order_by(PersonalTelegramAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[PersonalTelegramAccount]:
        result = await self.session.execute(
            select(PersonalTelegramAccount)
            .where(PersonalTelegramAccount.status == PersonalTelegramAccountStatus.active)
            .order_by(PersonalTelegramAccount.updated_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        client_id: int,
        project_id: int,
        display_name: str | None = None,
        username: str | None = None,
        phone: str | None = None,
        session_payload: str | None = None,
    ) -> PersonalTelegramAccount:
        account = PersonalTelegramAccount(
            client_id=client_id,
            project_id=project_id,
            display_name=display_name,
            username=username,
            phone=phone,
            session_payload=session_payload,
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(
        self,
        account: PersonalTelegramAccount,
        **fields: object,
    ) -> PersonalTelegramAccount:
        for key, value in fields.items():
            setattr(account, key, value)
        account.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def set_status(
        self,
        account: PersonalTelegramAccount,
        status: PersonalTelegramAccountStatus,
        *,
        last_error: str | None = None,
    ) -> PersonalTelegramAccount:
        account.status = status
        account.last_error = last_error
        account.updated_at = datetime.utcnow()
        if status == PersonalTelegramAccountStatus.active:
            account.last_connected_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def bulk_set_status(
        self,
        accounts: Sequence[int],
        status: PersonalTelegramAccountStatus,
    ) -> None:
        if not accounts:
            return
        await self.session.execute(
            update(PersonalTelegramAccount)
            .where(PersonalTelegramAccount.id.in_(accounts))
            .values(status=status.value, updated_at=datetime.utcnow())
        )
        await self.session.commit()

    async def delete(self, account: PersonalTelegramAccount) -> None:
        await self.session.delete(account)
        await self.session.commit()
