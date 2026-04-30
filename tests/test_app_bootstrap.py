from fastapi import FastAPI


def test_app_is_constructed(app: FastAPI):
    assert app.title == "AI Recipe Project"
    assert len(app.routes) >= 100


def test_health_endpoint(client, api_prefix: str):
    response = client.get(f"{api_prefix}/auth/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "AI Recipe Project"
    assert "/api/v1/auth/health" in schema["paths"]
