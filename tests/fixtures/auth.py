from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.builders.user_context import build_user_context


@pytest.fixture()
def authenticated_client(app: FastAPI) -> Iterator[TestClient]:
    from app.core.security.security import get_current_user

    async def fake_current_user():
        return build_user_context()

    app.dependency_overrides[get_current_user] = fake_current_user
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def superuser_client(app: FastAPI) -> Iterator[TestClient]:
    from app.core.security.security import get_current_user

    async def fake_current_user():
        return build_user_context(is_superuser=True, permissions=["*"])

    app.dependency_overrides[get_current_user] = fake_current_user
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
