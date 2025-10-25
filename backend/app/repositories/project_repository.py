from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.enums import AutoReplyMode


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_client(self, client_id: int) -> list[Project]:
        stmt = select(Project).where(Project.client_id == client_id).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, project_id: int) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, client_id: int, slug: str) -> Project | None:
        stmt = select(Project).where(Project.client_id == client_id, Project.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_bot_id(self, bot_id: int) -> Project | None:
        stmt = select(Project).where(Project.bot_id == bot_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(self, project_ids: Iterable[int]) -> list[Project]:
        ids = list(project_ids)
        if not ids:
            return []
        stmt = select(Project).where(Project.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        client_id: int,
        name: str,
        slug: str | None = None,
        description: str | None = None,
        status: str = "active",
        bot_id: int | None = None,
        filter_keywords: str | None = None,
        require_reply_for_sources: bool = False,
        hide_system_messages: bool = True,
        auto_reply_enabled: bool = False,
        auto_reply_mode=None,
        auto_reply_always: bool = False,
        auto_reply_start_time=None,
        auto_reply_end_time=None,
        auto_reply_timezone: str | None = None,
        auto_reply_text: str | None = None,
        topic_intro_template: str | None = None,
    ) -> Project:
        project = Project(
            client_id=client_id,
            name=name,
            slug=slug,
            description=description,
            status=status,
            bot_id=bot_id,
            filter_keywords=filter_keywords,
            require_reply_for_sources=require_reply_for_sources,
            hide_system_messages=hide_system_messages,
            auto_reply_enabled=auto_reply_enabled,
            auto_reply_mode=auto_reply_mode or AutoReplyMode.always,
            auto_reply_always=auto_reply_always,
            auto_reply_start_time=auto_reply_start_time,
            auto_reply_end_time=auto_reply_end_time,
            auto_reply_timezone=auto_reply_timezone,
            auto_reply_text=auto_reply_text,
            topic_intro_template=topic_intro_template,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(self, project: Project, **updates) -> Project:
        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.commit()
