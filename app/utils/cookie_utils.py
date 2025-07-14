# app/core/security/cookie_utils.py

from fastapi import Response
from app.config.settings import settings


def get_refresh_cookie_params(refresh_token: str):
    refresh_cookie_params = {
        "key": "refresh_token",
        "value": refresh_token,
        "httponly": True,
        "secure": settings.server.env == "production",
        "samesite": "lax",
        "max_age": 7 * 24 * 60 * 60
    }

    return refresh_cookie_params
