import pytest

from tests.helpers.http import concrete_path, parametrize_openapi_operations, request_kwargs_for_operation


ALLOWED_ANONYMOUS_REJECTION_STATUSES = {401, 403, 422}


def pytest_generate_tests(metafunc):
    parametrize_openapi_operations(metafunc, protected=True)


def test_protected_endpoints_reject_anonymous_requests(client, method: str, path: str, operation: dict):
    response = client.request(
        method,
        concrete_path(path),
        **request_kwargs_for_operation(operation),
    )

    assert response.status_code in ALLOWED_ANONYMOUS_REJECTION_STATUSES
    assert response.status_code != 500
