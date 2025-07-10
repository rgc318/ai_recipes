# app/core/request_scope.py
import contextvars

request_scope = contextvars.ContextVar("request_scope")

def set_request_scope(scope: dict):
    request_scope.set(scope)

def get_request_scope() -> dict:
    return request_scope.get({})
