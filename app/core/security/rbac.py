# app/core/security/rbac.py

from fastapi import Depends, HTTPException
from app.models.users.user import User
from app.core.security.security import get_current_user

def require_permission(permission: str):
    async def checker(user: User = Depends(get_current_user)):
        if permission not in user.permissions:
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
        return user
    return checker