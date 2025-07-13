# app/api/dependencies/permissions.py

from fastapi import Depends, HTTPException
from app.core.security.security import get_current_user
from app.models.user import User

def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user

def require_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified")
    return user
