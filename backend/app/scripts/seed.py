import asyncio

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.repositories.client_repository import ClientRepository
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService
from app.models.enums import UserRole
from app.models.user import User


async def seed() -> None:
    await init_db()
    async with SessionLocal() as session:
        auth = AuthService(session)
        admin = await auth.bootstrap_admin(
            settings.admin_account_email,
            settings.admin_basic_password,
            settings.admin_account_name,
        )
        print(f"Админ: {admin.email}")
        client_repo = ClientRepository(session)
        client = await client_repo.get_by_name("Demo")
        if client is None:
            client = await client_repo.create("Demo")
            print("Создан клиент Demo")
        user_repo = UserRepository(session)
        existing = await user_repo.get_by_email("owner@demo.local")
        if existing is None:
            user = User(
                email="owner@demo.local",
                full_name="Demo Owner",
                role=UserRole.owner,
                client_id=client.id,
            )
            await user_repo.create(user)
            print("Создан владелец Demo")
        else:
            print("Пользователь owner@demo.local уже существует")

        tester_login = "tester5765053@tuberry.local"
        tester_password = "Tuberry5765!"
        tester_telegram_id = "5765053"
        tester = await user_repo.get_by_telegram_user_id(tester_telegram_id)

        if tester is None:
            tester_client = await client_repo.create("Tester 5765053")
            tester_user = User(
                email=tester_login,
                full_name="Tester 5765053",
                role=UserRole.owner,
                telegram_user_id=tester_telegram_id,
                client_id=tester_client.id,
            )
            await user_repo.create(tester_user, password=tester_password)
            print(f"Создан тестовый пользователь {tester_login}")
        else:
            tester.email = tester_login
            tester.hashed_password = AuthService.hash_password(tester_password)
            if tester.client_id is None:
                tester_client = await client_repo.create("Tester 5765053")
                tester.client_id = tester_client.id
            await session.commit()
            await session.refresh(tester)
            print(f"Обновлён тестовый пользователь {tester_login}")
        print("Инициализация завершена")


if __name__ == "__main__":
    asyncio.run(seed())
