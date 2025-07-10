# app/core/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.request_scope import set_request_scope

class RequestScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scope = {
            "user_id": request.headers.get("X-User-Id"),
            "tenant_id": request.headers.get("X-Tenant-Id"),
        }
        set_request_scope(scope)
        response = await call_next(request)
        return response
