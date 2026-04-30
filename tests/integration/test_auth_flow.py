import pytest
from fastapi.testclient import TestClient

from app.enums.response_codes import ResponseCodeEnum


pytestmark = pytest.mark.integration


@pytest.fixture()
def auth_flow_client(integration_client: TestClient):
    original_headers = dict(integration_client.headers)
    original_cookies = dict(integration_client.cookies)

    integration_client.headers.pop("Authorization", None)
    integration_client.cookies.clear()

    yield integration_client

    integration_client.headers.clear()
    integration_client.headers.update(original_headers)
    integration_client.cookies.clear()
    for key, value in original_cookies.items():
        integration_client.cookies.set(key, value)


def login(client: TestClient, credentials: tuple[str, str]):
    username, password = credentials
    return client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )


def test_login_success_returns_access_token_and_refresh_cookie(
    auth_flow_client,
    integration_credentials,
):
    response = login(auth_flow_client, integration_credentials)

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == ResponseCodeEnum.SUCCESS.code
    assert payload["data"]["access_token"]
    assert payload["data"]["expires_at"]
    assert auth_flow_client.cookies.get("refresh_token")


def test_login_with_wrong_password_returns_business_error(
    auth_flow_client,
    integration_credentials,
):
    username, _ = integration_credentials
    response = auth_flow_client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": "definitely-wrong-password",
        },
    )

    assert response.status_code == 200
    assert response.json()["code"] == ResponseCodeEnum.LOGIN_FAILED.code


def test_refresh_token_without_cookie_returns_business_error(auth_flow_client):
    auth_flow_client.cookies.clear()

    response = auth_flow_client.post("/api/v1/auth/refresh-token")

    assert response.status_code == 200
    assert response.json()["code"] == ResponseCodeEnum.TOKEN_REFRESH_FAILED.code


def test_refresh_token_rotates_access_token_and_refresh_cookie(
    auth_flow_client,
    integration_credentials,
):
    login_response = login(auth_flow_client, integration_credentials)
    old_refresh_token = auth_flow_client.cookies.get("refresh_token")

    response = auth_flow_client.post("/api/v1/auth/refresh-token")

    assert login_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == ResponseCodeEnum.SUCCESS.code
    assert payload["data"]["access_token"]
    assert auth_flow_client.cookies.get("refresh_token")
    assert auth_flow_client.cookies.get("refresh_token") != old_refresh_token


def test_logout_revokes_access_token_and_clears_refresh_cookie(
    auth_flow_client,
    integration_credentials,
):
    login_response = login(auth_flow_client, integration_credentials)
    access_token = login_response.json()["data"]["access_token"]

    response = auth_flow_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == ResponseCodeEnum.SUCCESS.code
    assert auth_flow_client.cookies.get("refresh_token") is None
