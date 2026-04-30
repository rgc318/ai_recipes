def test_login_rejects_missing_payload_before_service_call(client, api_prefix: str):
    response = client.post(f"{api_prefix}/auth/login", json={})

    assert response.status_code == 422


def test_register_rejects_invalid_payload_before_service_call(client, api_prefix: str):
    response = client.post(
        f"{api_prefix}/auth/register",
        json={
            "username": "ab",
            "password": "short",
            "email": "not-an-email",
        },
    )

    assert response.status_code == 422
