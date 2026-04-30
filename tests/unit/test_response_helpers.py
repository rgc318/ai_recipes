import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from app.enums.response_codes import ResponseCodeEnum
from app.schemas.common.api_response import response_error, response_success, to_json_compatible


class ExamplePayload(BaseModel):
    id: UUID
    created_at: datetime


def response_json(response):
    return json.loads(response.body.decode())


def test_response_success_uses_standard_envelope_and_encodes_pydantic_payload():
    payload = ExamplePayload(
        id=UUID("00000000-0000-0000-0000-000000000123"),
        created_at=datetime(2026, 1, 1, 8, 30, tzinfo=UTC),
    )

    response = response_success(data=payload, message="ok")

    assert response.status_code == 200
    assert response_json(response) == {
        "code": ResponseCodeEnum.SUCCESS.code,
        "message": "ok",
        "data": {
            "id": "00000000-0000-0000-0000-000000000123",
            "created_at": "2026-01-01T08:30:00+00:00",
        },
    }


def test_response_error_uses_standard_envelope():
    response = response_error(code=ResponseCodeEnum.FORBIDDEN, http_status=403)

    assert response.status_code == 403
    assert response_json(response) == {
        "code": ResponseCodeEnum.FORBIDDEN.code,
        "message": ResponseCodeEnum.FORBIDDEN.message,
        "data": None,
    }


def test_response_cookie_parameters_are_not_mutated():
    cookie_params = {
        "key": "refresh_token",
        "value": "token",
        "httponly": True,
        "path": "/",
    }

    response = response_success(data=True, set_cookies=[cookie_params])

    assert "refresh_token=token" in response.headers["set-cookie"]
    assert cookie_params == {
        "key": "refresh_token",
        "value": "token",
        "httponly": True,
        "path": "/",
    }


def test_to_json_compatible_recursively_serializes_pydantic_models():
    payload = ExamplePayload(
        id=UUID("00000000-0000-0000-0000-000000000456"),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert to_json_compatible({"items": [payload]}) == {
        "items": [
            {
                "id": UUID("00000000-0000-0000-0000-000000000456"),
                "created_at": datetime(2026, 1, 2, tzinfo=UTC),
            }
        ]
    }
