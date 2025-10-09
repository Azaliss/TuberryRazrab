from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models.settings import ProjectSettings


class ProjectSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> ProjectSettings:
        result = await self.session.execute(select(ProjectSettings).limit(1))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = ProjectSettings(
                master_bot_token=app_settings.master_bot_token or None,
                master_bot_name=app_settings.master_bot_name or None,
            )
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        return settings

    async def update(self, settings_obj: ProjectSettings, **kwargs) -> ProjectSettings:
        for key, value in kwargs.items():
            if hasattr(settings_obj, key):
                setattr(settings_obj, key, value)
        settings_obj.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(settings_obj)
        return settings_obj
