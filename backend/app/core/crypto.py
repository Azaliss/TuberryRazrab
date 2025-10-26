from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _get_fernet() -> Fernet:
    secret = settings.personal_telegram_session_secret or settings.app_secret
    return Fernet(_derive_key(secret))


def encrypt_payload(payload: str | bytes) -> str:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    token = _get_fernet().encrypt(data)
    return token.decode("utf-8")


def decrypt_payload(token: str | bytes) -> str:
    raw_token = token.encode("utf-8") if isinstance(token, str) else token
    try:
        decrypted = _get_fernet().decrypt(raw_token)
    except InvalidToken as exc:  # noqa: BLE001
        raise ValueError("Invalid encrypted payload") from exc
    return decrypted.decode("utf-8")
