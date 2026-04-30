import pytest


@pytest.mark.xfail(reason="app.main currently overrides get_current_user globally with a None mock user.")
def test_anonymous_user_context_request_is_rejected(client, api_prefix: str):
    response = client.get(f"{api_prefix}/user/me")

    assert response.status_code in {401, 403}


@pytest.mark.xfail(reason="global mock user currently causes permission dependencies to raise 500 instead of 401/403.")
def test_anonymous_admin_request_is_rejected_without_500(client, api_prefix: str):
    response = client.get(f"{api_prefix}/role/")

    assert response.status_code in {401, 403}
