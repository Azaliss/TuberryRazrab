from __future__ import annotations

from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.repositories.client_repository import ClientRepository
from app.repositories.dialog_repository import DialogRepository
from app.schemas.client import ClientCreateRequest, ClientResponse, ClientUpdateRequest

router = APIRouter()


@router.get("/me", response_model=ClientResponse)
async def get_my_client(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not assigned")
    client = await ClientRepository(session).get_by_id(user.client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/me", response_model=ClientResponse)
async def update_my_client(
    payload: ClientUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not assigned")
    repo = ClientRepository(session)
    client = await repo.get_by_id(user.client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    was_enabled = client.auto_reply_enabled
    update_payload = _prepare_client_update_payload(client, payload)
    client = await repo.update(client, **update_payload)
    if client.auto_reply_enabled and not was_enabled:
        dialog_repo = DialogRepository(session)
        await dialog_repo.reset_auto_reply_marks_for_client(client.id)
    return client


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    clients = await ClientRepository(session).list()
    return clients


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    repo = ClientRepository(session)

    auto_reply_text = payload.auto_reply_text.strip() if payload.auto_reply_text else None
    auto_reply_timezone = payload.auto_reply_timezone.strip() if payload.auto_reply_timezone else None
    auto_reply_enabled = bool(payload.auto_reply_enabled)
    auto_reply_always = bool(payload.auto_reply_always)
    auto_reply_start_time = payload.auto_reply_start_time
    auto_reply_end_time = payload.auto_reply_end_time
    if auto_reply_timezone:
        try:
            ZoneInfo(auto_reply_timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Указан неверный часовой пояс") from exc

    if auto_reply_enabled:
        if not auto_reply_timezone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите часовой пояс для автоответа")
        if not auto_reply_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите текст автоответа")
        if not auto_reply_always:
            if auto_reply_start_time is None or auto_reply_end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Укажите время начала и окончания автоответа",
                )
            if auto_reply_start_time == auto_reply_end_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Время начала и окончания не могут совпадать",
                )

    client = await repo.create(
        name=payload.name,
        plan=payload.plan or "default",
        filter_keywords=payload.filter_keywords,
        require_reply_for_avito=payload.require_reply_for_avito or False,
        hide_system_messages=payload.hide_system_messages if payload.hide_system_messages is not None else True,
        auto_reply_enabled=auto_reply_enabled,
        auto_reply_always=auto_reply_always,
        auto_reply_start_time=auto_reply_start_time,
        auto_reply_end_time=auto_reply_end_time,
        auto_reply_timezone=auto_reply_timezone,
        auto_reply_text=auto_reply_text,
    )
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdateRequest,
    session: AsyncSession = Depends(deps.get_db),
    _: object = Depends(deps.get_current_admin),
):
    repo = ClientRepository(session)
    client = await repo.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    was_enabled = client.auto_reply_enabled
    update_payload = _prepare_client_update_payload(client, payload)
    client = await repo.update(client, **update_payload)
    if client.auto_reply_enabled and not was_enabled:
        dialog_repo = DialogRepository(session)
        await dialog_repo.reset_auto_reply_marks_for_client(client.id)
    return client


def _prepare_client_update_payload(client, payload: ClientUpdateRequest) -> Dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)

    if "auto_reply_text" in updates:
        text_value = updates["auto_reply_text"]
        if text_value is not None:
            trimmed = text_value.strip()
            updates["auto_reply_text"] = trimmed or None
        else:
            updates["auto_reply_text"] = None

    if "auto_reply_timezone" in updates:
        tz_value = updates["auto_reply_timezone"]
        if tz_value is not None:
            updates["auto_reply_timezone"] = tz_value.strip() or None

    enabled = updates.get("auto_reply_enabled", client.auto_reply_enabled)
    always = updates.get("auto_reply_always", client.auto_reply_always)
    start_time = updates.get("auto_reply_start_time", client.auto_reply_start_time)
    end_time = updates.get("auto_reply_end_time", client.auto_reply_end_time)
    timezone = updates.get("auto_reply_timezone", client.auto_reply_timezone)
    text_for_validation: str = ""
    if "auto_reply_text" in updates:
        text_for_validation = updates["auto_reply_text"] or ""
    else:
        text_for_validation = (client.auto_reply_text or "").strip()

    if timezone:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Указан неверный часовой пояс") from exc
    elif enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите часовой пояс для автоответа")

    if enabled:
        if not text_for_validation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите текст автоответа")
        if not always:
            if start_time is None or end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Укажите время начала и окончания автоответа",
                )
            if start_time == end_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Время начала и окончания не могут совпадать",
                )

    return updates
