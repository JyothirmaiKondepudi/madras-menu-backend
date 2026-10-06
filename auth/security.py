"""
Password hashing and JWT issuance/verification — the two crypto primitives
everything else in this package builds on. No DB access here on purpose,
so this stays trivially unit-testable and has no import-order dependency
on models/services.

bcrypt is used directly, not via passlib: passlib's bcrypt backend has a
real, documented incompatibility with bcrypt>=4.1 (MissingBackendError,
since newer bcrypt dropped the __about__.__version__ attribute passlib's
version-sniffing relies on). PyJWT is used instead of python-jose for a
simpler API and to avoid python-jose's history of algorithm-confusion
CVEs — jwt.decode below always pins `algorithms=[JWT_ALGORITHM]` rather
than trusting the token's own header.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from config import get_settings

# SECRET_KEY, JWT_ALGORITHM and JWT_EXPIRE_MINUTES come from config.py and are
# read when a token is signed or checked, so scripts that only hash passwords
# don't need them. No refresh-token flow yet, so JWT_EXPIRE_MINUTES defaults
# to a day's work (720), not short-lived-access-token length.


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: UUID, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else settings.JWT_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    """Raises jwt.PyJWTError (expired, malformed, bad signature, etc.) on
    any failure — auth/dependencies.py is the one place that catches it and
    turns it into a 401."""
    settings = get_settings()
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    return UUID(payload["sub"])
