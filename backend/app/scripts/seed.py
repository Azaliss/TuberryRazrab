import asyncio

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
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
        project_repo = ProjectRepository(session)

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

        projects = await project_repo.list_for_client(client.id)
        if not projects:
            project = await project_repo.create(
                client_id=client.id,
                name="Demo Project",
                description="Стартовый проект для демонстрации возможностей Tuberry",
                status="active",
                require_reply_for_sources=False,
                hide_system_messages=True,
            )
            print(f"Создан проект {project.name}")
        else:
            print("У клиента Demo уже есть проекты")

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
