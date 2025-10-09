import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.repositories.dialog_repository import DialogRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.dialog import (
    DialogMessageCreateRequest,
    DialogMessageSendResponse,
    DialogMessagesResponse,
    DialogResponse,
)
from app.services.dialog import DialogService

router = APIRouter()


@router.get("/", response_model=list[DialogResponse])
async def list_dialogs(
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=400, detail="User not attached to client")
    dialogs = await DialogRepository(session).list_for_client(user.client_id)
    return dialogs


@router.get("/{dialog_id}", response_model=DialogMessagesResponse)
async def get_dialog(
    dialog_id: int,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    repo = DialogRepository(session)
    dialog = await repo.get(dialog_id)
    if dialog is None or dialog.client_id != user.client_id:
        raise HTTPException(status_code=404, detail="Dialog not found")
    messages = await MessageRepository(session).list_for_dialog(dialog_id)
    return DialogMessagesResponse(
        dialog=dialog,
        messages=[
            {
                "id": m.id,
                "direction": m.direction,
                "body": m.body,
                "status": m.status,
                "created_at": m.created_at,
                "attachments": _safe_load_attachments(m.attachments),
            }
            for m in messages
        ],
    )


def _safe_load_attachments(raw: str | None) -> list | dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@router.post("/{dialog_id}/messages", response_model=DialogMessageSendResponse, status_code=status.HTTP_201_CREATED)
async def send_dialog_message(
    dialog_id: int,
    payload: DialogMessageCreateRequest,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_current_user),
):
    if user.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not attached to client")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текст сообщения не может быть пустым")

    dialog_repo = DialogRepository(session)
    dialog = await dialog_repo.get(dialog_id)
    if dialog is None or dialog.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dialog not found")

    service = DialogService(session)
    try:
        result = await service.send_portal_text_message(dialog=dialog, text=text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DialogMessageSendResponse(**result)
