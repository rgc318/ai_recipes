import pytest


pytestmark = pytest.mark.integration


def test_integration_login_state_is_cached_for_session(integration_auth_state):
    assert integration_auth_state.access_token
    assert integration_auth_state.username


def test_integration_authenticated_client_reuses_login_state(
    integration_authenticated_client,
    integration_auth_state,
):
    response = integration_authenticated_client.get("/api/v1/user/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["username"] == integration_auth_state.username
