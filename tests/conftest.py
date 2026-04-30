import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


os.environ.setdefault("ENV", "test")

pytest_plugins = (
    "tests.fixtures.auth",
    "tests.fixtures.integration_auth",
)


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    app.dependency_overrides.clear()
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def api_prefix() -> str:
    return "/api/v1"


@pytest.fixture(scope="session")
def route_map(app: FastAPI) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods:
            routes.add((method, path))
    return routes


def pytest_collection_modifyitems(config, items):
    markers_by_path = {
        "/contract/": "contract",
        "/security/": "security",
        "/unit/": "unit",
        "/integration/": "integration",
    }

    for item in items:
        path = item.path.as_posix()
        for path_fragment, marker_name in markers_by_path.items():
            if path_fragment in path:
                item.add_marker(getattr(pytest.mark, marker_name))
                break
