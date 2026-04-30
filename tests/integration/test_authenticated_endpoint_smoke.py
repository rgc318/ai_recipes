import pytest

from tests.helpers.http import concrete_path, parametrize_openapi_operations, request_kwargs_for_operation


pytestmark = pytest.mark.integration

ALLOWED_AUTHENTICATED_STATUSES = {200, 201, 204, 400, 403, 404, 422}
EXCLUDED_AUTHENTICATED_SMOKE_ENDPOINTS = {
    ("POST", "/api/v1/auth/logout"),
}


def pytest_generate_tests(metafunc):
    parametrize_openapi_operations(
        metafunc,
        protected=True,
        excluded_endpoints=EXCLUDED_AUTHENTICATED_SMOKE_ENDPOINTS,
    )


def test_authenticated_protected_endpoints_are_reachable_without_auth_failures(
    integration_authenticated_client,
    method: str,
    path: str,
    operation: dict,
):
    response = integration_authenticated_client.request(
        method,
        concrete_path(path),
        **request_kwargs_for_operation(operation),
    )

    assert response.status_code in ALLOWED_AUTHENTICATED_STATUSES
    assert response.status_code not in {401, 500}
