from typing import Any

import pytest


SAMPLE_UUID = "00000000-0000-0000-0000-000000000001"
SAMPLE_STEP_ID = "1"


def concrete_path(path_template: str) -> str:
    return (
        path_template
        .replace("{recipe_id}", SAMPLE_UUID)
        .replace("{image_record_id}", SAMPLE_UUID)
        .replace("{category_id}", SAMPLE_UUID)
        .replace("{permission_id}", SAMPLE_UUID)
        .replace("{role_id}", SAMPLE_UUID)
        .replace("{unit_id}", SAMPLE_UUID)
        .replace("{user_id}", SAMPLE_UUID)
        .replace("{record_id}", SAMPLE_UUID)
        .replace("{ingredient_id}", SAMPLE_UUID)
        .replace("{tag_id}", SAMPLE_UUID)
        .replace("{step_id}", SAMPLE_STEP_ID)
    )


def request_kwargs_for_operation(operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody")
    if not request_body:
        return {}

    content = request_body.get("content", {})
    if "application/json" in content:
        return {"json": {}}
    if "multipart/form-data" in content:
        return {"files": {}}
    if "application/x-www-form-urlencoded" in content:
        return {"data": {}}

    return {}


def openapi_operations(
    schema: dict,
    *,
    protected: bool | None = None,
    excluded_endpoints: set[tuple[str, str]] | None = None,
) -> list[Any]:
    excluded_endpoints = excluded_endpoints or set()
    params = []
    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue

        for method, operation in path_item.items():
            method_upper = method.upper()
            if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue

            has_security = bool(operation.get("security"))
            if protected is True and not has_security:
                continue
            if protected is False and has_security:
                continue
            if (method_upper, path) in excluded_endpoints:
                continue

            params.append(
                pytest.param(
                    method_upper,
                    path,
                    operation,
                    id=f"{method_upper} {path}",
                )
            )

    return params


def parametrize_openapi_operations(
    metafunc,
    *,
    protected: bool | None = None,
    excluded_endpoints: set[tuple[str, str]] | None = None,
) -> None:
    if {"method", "path", "operation"} <= set(metafunc.fixturenames):
        from app.main import app
        from fastapi.testclient import TestClient

        schema = TestClient(app, raise_server_exceptions=False).get("/openapi.json").json()
        metafunc.parametrize(
            ("method", "path", "operation"),
            openapi_operations(schema, protected=protected, excluded_endpoints=excluded_endpoints),
        )
