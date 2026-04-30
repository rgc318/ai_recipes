import os
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient


@dataclass(frozen=True)
class IntegrationAuthState:
    access_token: str
    username: str

    @property
    def authorization_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest.fixture(scope="session")
def integration_credentials() -> tuple[str, str]:
    username = os.getenv("TEST_AUTH_USERNAME")
    password = os.getenv("TEST_AUTH_PASSWORD")
    if not username or not password:
        pytest.skip("TEST_AUTH_USERNAME and TEST_AUTH_PASSWORD are required for integration auth tests")
    return username, password


@pytest.fixture(scope="session")
def integration_client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def integration_auth_state(
    integration_client: TestClient,
    integration_credentials: tuple[str, str],
) -> IntegrationAuthState:
    username, password = integration_credentials
    response = integration_client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["access_token"]
    assert integration_client.cookies.get("refresh_token")

    return IntegrationAuthState(
        access_token=payload["data"]["access_token"],
        username=username,
    )


@pytest.fixture(scope="session")
def integration_authenticated_client(
    integration_client: TestClient,
    integration_auth_state: IntegrationAuthState,
) -> TestClient:
    integration_client.headers.update(integration_auth_state.authorization_header)
    return integration_client
