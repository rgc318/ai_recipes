# app/utils/jwt_utils.py

from datetime import datetime, timedelta, UTC
from typing import Tuple, Literal, Optional
import uuid
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, PyJWTError

from app.config.settings import settings
from app.core.exceptions import TokenRevokedException, TokenExpiredException, InvalidTokenException, \
    TokenTypeMismatchException
# 2. 导入新的全局 redis_factory 实例
from app.infra.redis.redis_factory import redis_factory
ALGORITHM = settings.security_settings.jwt_algorithm or "HS256"
ISSUER = settings.security_settings.jwt_issuer or "ai-recipes"
AUDIENCE = settings.security_settings.jwt_audience or None


# =====================
# Token 生成
# =====================

def create_token(
    data: dict,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh"] = "access",
) -> Tuple[str, timedelta, str]:
    """
    返回 (token, expires_delta, jti)
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
        # 检查 access token 是否被 revoke
        if payload.get("type") == "access":
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
# Access Token
# =====================

def create_access_token(data: dict, remember_me=False) -> Tuple[str, timedelta, str]:
    """
    创建 access token (无状态，不存 Redis)
    """
    delta = timedelta(days=14) if remember_me else timedelta(minutes=settings.security_settings.token_expire_minutes)
    return create_token(data, delta, "access")

# =====================
# Refresh Token
# =====================

async def create_refresh_token(data: dict, user_id: str) -> Tuple[str, timedelta, str]:
    """
    创建 refresh token 并存储到 Redis
    """
    token, expires_delta, jti = create_token(data, timedelta(days=7), "refresh")

    redis = redis_factory.get_client('default')
    key = f"refresh:{user_id}:{jti}"
    await redis.set(
        key,
        token,
        ex=int(expires_delta.total_seconds())
    )
    return token, expires_delta, jti

# =====================
# Refresh Token rotation
# =====================

async def rotate_refresh_token(old_jti: str, user_id: str, data: dict) -> Tuple[str, timedelta, str]:
    """
    撤销旧 refresh token（删除 Redis key），生成新 refresh token
    """
    redis = redis_factory.get_client('default')
    old_key_pattern = f"refresh:{user_id}:{old_jti}"

    # 检查旧 token 是否存在（防止被重复使用）
    exists = await redis.exists(old_key_pattern)
    if not exists:
        raise InvalidTokenException(message="Refresh Token 已被使用或无效")

    # 删除旧 token
    await redis.delete(old_key_pattern)

    # 生成新 token
    return await create_refresh_token(data, user_id)

# =====================
# Token revoke / blacklist
# =====================

async def revoke_token(jti: str, expires_in: Optional[int] = None):
    """
    将 access token jti 加入 Redis blacklist
    """
    redis = redis_factory.get_client('default')
    ex = expires_in or (7 * 24 * 3600)
    await redis.set(f"revoked:{jti}", "1", ex=ex)

async def is_token_revoked(jti: str) -> bool:
    """
    检查 access token jti 是否被撤销
    """
    redis = redis_factory.get_client('default')
    return await redis.exists(f"revoked:{jti}") == 1
