def test_anonymous_user_context_request_is_rejected(client, api_prefix: str):
    response = client.get(f"{api_prefix}/user/me")

    assert response.status_code in {401, 403}


def test_anonymous_admin_request_is_rejected_without_500(client, api_prefix: str):
    response = client.get(f"{api_prefix}/role/")

    assert response.status_code in {401, 403}


def test_invalid_bearer_token_is_rejected(client, api_prefix: str):
    response = client.get(
        f"{api_prefix}/user/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


def test_authenticated_user_context_can_be_overridden_in_tests(authenticated_client, api_prefix: str):
    response = authenticated_client.get(f"{api_prefix}/user/me")

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "test-user"
