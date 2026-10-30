import time
import warnings
from typing import Any

from app.core.config import settings

warnings.filterwarnings("ignore", module="authlib")
from authlib.jose import JoseError, JsonWebToken  # noqa: E402
from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
jwt_engine = JsonWebToken([settings.ALGORITHM])
ALGORITHM = settings.ALGORITHM


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta_seconds: int | None = None) -> str:
    to_encode = data.copy()
    now = int(time.time())
    expire = now + (
        expires_delta_seconds
        if expires_delta_seconds is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    to_encode.update({"iat": now, "exp": expire, "type": "access"})
    header = {"alg": settings.ALGORITHM, "typ": "JWT"}
    token = jwt_engine.encode(header, to_encode, settings.SECRET_KEY.encode("utf-8"))
    return token.decode("utf-8") if isinstance(token, bytes) else str(token)


def create_refresh_token(data: dict[str, Any], expires_delta_seconds: int | None = None) -> str:
    to_encode = data.copy()
    now = int(time.time())
    expire = now + (
        expires_delta_seconds
        if expires_delta_seconds is not None
        else settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    to_encode.update({"iat": now, "exp": expire, "type": "refresh"})
    header = {"alg": settings.ALGORITHM, "typ": "JWT"}
    token = jwt_engine.encode(header, to_encode, settings.SECRET_KEY.encode("utf-8"))
    return token.decode("utf-8") if isinstance(token, bytes) else str(token)


def verify_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt_engine.decode(token, settings.SECRET_KEY.encode("utf-8"))
        claims.validate()
        return dict(claims)
    except JoseError as exc:
        raise ValueError(f"Token validation failed: {str(exc)}") from exc
