from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import uuid
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from app.core.config import get_settings

_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
_settings = get_settings()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=_settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=[_settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        from app.core.exceptions import TokenExpiredError
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError("Invalid token.")


def generate_id(prefix: str = "") -> str:
    uid = str(uuid.uuid4()).replace("-", "")[:20]
    return f"{prefix}{uid}" if prefix else uid
