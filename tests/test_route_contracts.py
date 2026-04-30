def test_core_route_contracts_are_registered(route_map: set[tuple[str, str]]):
    expected_routes = {
        ("GET", "/api/v1/auth/health"),
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/recipes/"),
        ("POST", "/api/v1/recipes/"),
        ("GET", "/api/v1/tags/"),
        ("GET", "/api/v1/ingredients/"),
        ("GET", "/api/v1/units/"),
        ("GET", "/api/v1/categories/tree"),
        ("POST", "/api/v1/file/presigned-url/generate"),
        ("POST", "/api/v1/file/register"),
    }

    assert expected_routes <= route_map


def test_removed_legacy_routes_are_not_registered(route_map: set[tuple[str, str]]):
    legacy_routes = {
        ("GET", "/minio/test-connection"),
        ("POST", "/upload-avatar"),
        ("POST", "/upload-recipe-image"),
        ("POST", "/minio/upload"),
        ("GET", "/api/recipes"),
        ("POST", "/api/auth/login"),
    }

    assert route_map.isdisjoint(legacy_routes)


import pytest


@pytest.mark.xfail(reason="permission_router registers POST /permission/sync-from-source twice.")
def test_no_duplicate_method_path_routes(app):
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()

    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods:
            key = (method, path)
            if key in seen:
                duplicates.add(key)
            seen.add(key)

    assert duplicates == set()
