import pytest

from tests.helpers.http import concrete_path, parametrize_openapi_operations, request_kwargs_for_operation


pytestmark = pytest.mark.integration


def pytest_generate_tests(metafunc):
    parametrize_openapi_operations(metafunc, protected=False)


def test_public_endpoints_do_not_return_unhandled_errors(
    integration_client,
    method: str,
    path: str,
    operation: dict,
):
    response = integration_client.request(
        method,
        concrete_path(path),
        **request_kwargs_for_operation(operation),
    )

    assert response.status_code < 500
