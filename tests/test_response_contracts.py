def test_standard_health_response_is_plain_status_payload(client, api_prefix: str):
    response = client.get(f"{api_prefix}/auth/health")

    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == "ok"


def test_unknown_route_returns_fastapi_404(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
