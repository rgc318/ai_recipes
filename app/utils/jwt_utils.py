# app/utils/jwt_utils.py

from datetime import datetime, timedelta, UTC
from typing import Tuple, Literal, Optional
import uuid
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, PyJWTError

from app.config.settings import settings
from app.utils.redis_client import RedisClient  # ✅ 修改这里
from app.core.global_exception import UnauthorizedException

ALGORITHM = settings.security_settings.jwt_algorithm or "HS256"
ISSUER = settings.security_settings.jwt_issuer or "ai-recipes"
AUDIENCE = settings.security_settings.jwt_audience or None  # 可选

# =====================
# 自定义异常
# =====================

class TokenExpiredException(UnauthorizedException):
    code = "TOKEN_EXPIRED"
    message = "Token 已过期"

class InvalidTokenException(UnauthorizedException):
    code = "INVALID_TOKEN"
    message = "无效 Token"

class TokenRevokedException(UnauthorizedException):
    code = "TOKEN_REVOKED"
    message = "Token 已被吊销"

class TokenTypeMismatchException(UnauthorizedException):
    code = "TOKEN_TYPE_ERROR"
    message = "Token 类型错误"

# =====================
# Token 生成
# =====================

def create_token(
    data: dict,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh"] = "access",
) -> Tuple[str, timedelta, str]:
    """
    返回 token, expires_delta, jti
    """
    now = datetime.now(UTC)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    to_encode = {
        **data,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": ISSUER,
        "jti": jti,
        "type": token_type,
    }
    if AUDIENCE:
        to_encode["aud"] = AUDIENCE

    encoded = jwt.encode(to_encode, settings.security_settings.secret, algorithm=ALGORITHM)
    return encoded, expires_delta, jti

# =====================
# Token 解码
# =====================

async def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.security_settings.secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE if AUDIENCE else None,
        )
        # 检查 revoke
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            raise TokenRevokedException()
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredException()
    except InvalidTokenError as e:
        raise InvalidTokenException(message=str(e))
    except PyJWTError as e:
        raise InvalidTokenException(message=str(e))

# =====================
# Token 类型验证
# =====================

def validate_token_type(payload: dict, expected: str):
    if payload.get("type") != expected:
        raise TokenTypeMismatchException(message=f"应为 {expected}")

# =====================
# 快捷封装
# =====================

def create_access_token(data: dict, remember_me=False) -> Tuple[str, timedelta, str]:
    """
    创建 access token。

    Args:
        data: 要编码进 token 的数据，如 {"sub": user_id}
        remember_me: 如果为 True，则 token 有效期为 14 天，否则为默认设置时间

    Returns:
        (token 字符串, 过期时间, jti)
    """
    delta = timedelta(days=14) if remember_me else timedelta(minutes=settings.security_settings.token_expire_minutes)
    return create_token(data, delta, "access")

def create_refresh_token(data: dict) -> Tuple[str, timedelta, str]:
    return create_token(data, timedelta(days=7), "refresh")

# =====================
# Token revoke / blacklist
# =====================

async def revoke_token(jti: str, expires_in: Optional[int] = None):
    """
    将 jti 加入 Redis blacklist
    """
    redis = RedisClient.get_client()  # ✅ 修改为直接获取 Redis 实例
    ex = expires_in or (7 * 24 * 3600)  # 默认 7 天
    await redis.set(f"revoked:{jti}", "1", ex=ex)

async def is_token_revoked(jti: str) -> bool:
    """
    检查 jti 是否被撤销
    """
    redis = RedisClient.get_client()  # ✅ 修改为直接获取 Redis 实例
    return await redis.exists(f"revoked:{jti}") == 1

# =====================
# Refresh Token rotation
# =====================

async def rotate_refresh_token(old_jti: str, data: dict) -> Tuple[str, timedelta, str]:
    """
    撤销旧 refresh token，生成新 refresh token
    """
    if await is_token_revoked(old_jti):
        raise InvalidTokenException(message="Refresh Token 已被使用")
    await revoke_token(old_jti)
    return create_refresh_token(data)
