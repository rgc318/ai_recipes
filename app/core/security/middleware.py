# app/core/security/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 记录请求用户ID、IP、路径、method、trace_id
        response = await call_next(request)
        return response


