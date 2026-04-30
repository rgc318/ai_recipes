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


def test_static_routes_are_registered_before_matching_dynamic_routes(app):
    api_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/")
        and getattr(route, "methods", None)
    ]
    violations: list[str] = []

    for index, route in enumerate(api_routes):
        dynamic_path = route.path
        if "{" not in dynamic_path:
            continue

        dynamic_segments = dynamic_path.strip("/").split("/")
        for later_route in api_routes[index + 1:]:
            static_path = later_route.path
            if "{" in static_path:
                continue
            if not route.methods.intersection(later_route.methods):
                continue

            static_segments = static_path.strip("/").split("/")
            if len(dynamic_segments) != len(static_segments):
                continue

            matches = all(
                dynamic_segment.startswith("{") and dynamic_segment.endswith("}")
                or dynamic_segment == static_segment
                for dynamic_segment, static_segment in zip(dynamic_segments, static_segments)
            )
            if matches:
                methods = sorted(route.methods.intersection(later_route.methods))
                violations.append(f"{methods} {dynamic_path} before {static_path}")

    assert violations == []
