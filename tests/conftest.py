import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


os.environ.setdefault("ENV", "test")


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


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
