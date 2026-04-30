EXPECTED_API_ENDPOINTS = {
    ("DELETE", "/api/v1/categories/batch"),
    ("DELETE", "/api/v1/categories/permanent-delete"),
    ("DELETE", "/api/v1/categories/{category_id}"),
    ("DELETE", "/api/v1/file/files"),
    ("DELETE", "/api/v1/file_management/bulk/permanent"),
    ("DELETE", "/api/v1/file_management/bulk/soft"),
    ("DELETE", "/api/v1/file_management/{record_id}"),
    ("DELETE", "/api/v1/file_management/{record_id}/permanent"),
    ("DELETE", "/api/v1/ingredients/"),
    ("DELETE", "/api/v1/ingredients/permanent-delete"),
    ("DELETE", "/api/v1/ingredients/{ingredient_id}"),
    ("DELETE", "/api/v1/permission/permanent"),
    ("DELETE", "/api/v1/permission/{permission_id}"),
    ("DELETE", "/api/v1/recipes/batch"),
    ("DELETE", "/api/v1/recipes/permanent-delete"),
    ("DELETE", "/api/v1/recipes/{recipe_id}"),
    ("DELETE", "/api/v1/recipes/{recipe_id}/gallery-images/{image_record_id}"),
    ("DELETE", "/api/v1/recipes/{recipe_id}/steps/{step_id}/images/{image_record_id}"),
    ("DELETE", "/api/v1/role/"),
    ("DELETE", "/api/v1/role/permanent"),
    ("DELETE", "/api/v1/tags/batch"),
    ("DELETE", "/api/v1/tags/permanent-delete"),
    ("DELETE", "/api/v1/tags/{tag_id}"),
    ("DELETE", "/api/v1/units/batch"),
    ("DELETE", "/api/v1/units/permanent-delete"),
    ("DELETE", "/api/v1/units/{unit_id}"),
    ("DELETE", "/api/v1/user/batch"),
    ("DELETE", "/api/v1/user/permanent-deactivation"),
    ("DELETE", "/api/v1/user/{user_id}"),
    ("GET", "/api/v1/auth/health"),
    ("GET", "/api/v1/categories/"),
    ("GET", "/api/v1/categories/tree"),
    ("GET", "/api/v1/categories/{category_id}"),
    ("GET", "/api/v1/file/files"),
    ("GET", "/api/v1/file/files/exists"),
    ("GET", "/api/v1/file/presigned-url/get"),
    ("GET", "/api/v1/file_management/"),
    ("GET", "/api/v1/file_management/stats"),
    ("GET", "/api/v1/file_management/{record_id}"),
    ("GET", "/api/v1/ingredients/"),
    ("GET", "/api/v1/permission/"),
    ("GET", "/api/v1/permission/selector"),
    ("GET", "/api/v1/permission/{permission_id}"),
    ("GET", "/api/v1/recipes/"),
    ("GET", "/api/v1/recipes/{recipe_id}"),
    ("GET", "/api/v1/role/"),
    ("GET", "/api/v1/role/selector"),
    ("GET", "/api/v1/role/{role_id}"),
    ("GET", "/api/v1/tags/"),
    ("GET", "/api/v1/units/"),
    ("GET", "/api/v1/units/all"),
    ("GET", "/api/v1/user/"),
    ("GET", "/api/v1/user/info"),
    ("GET", "/api/v1/user/me"),
    ("GET", "/api/v1/user/{user_id}"),
    ("PATCH", "/api/v1/user/me"),
    ("PATCH", "/api/v1/user/me/avatar"),
    ("PATCH", "/api/v1/user/me/avatar/link-uploaded-file"),
    ("PATCH", "/api/v1/user/me/password"),
    ("PATCH", "/api/v1/user/{user_id}/avatar"),
    ("PATCH", "/api/v1/user/{user_id}/avatar/link-uploaded-file"),
    ("POST", "/api/v1/auth/change-password"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/refresh-token"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/reset-password"),
    ("POST", "/api/v1/categories/"),
    ("POST", "/api/v1/categories/merge"),
    ("POST", "/api/v1/categories/restore"),
    ("POST", "/api/v1/file/files/move"),
    ("POST", "/api/v1/file/presigned-url/generate"),
    ("POST", "/api/v1/file/presigned-url/policy"),
    ("POST", "/api/v1/file/presigned-url/put"),
    ("POST", "/api/v1/file/register"),
    ("POST", "/api/v1/file/upload/avatar"),
    ("POST", "/api/v1/file/upload/by_profile"),
    ("POST", "/api/v1/file_management/merge"),
    ("POST", "/api/v1/file_management/restore/bulk"),
    ("POST", "/api/v1/file_management/{record_id}/restore"),
    ("POST", "/api/v1/ingredients/"),
    ("POST", "/api/v1/ingredients/merge"),
    ("POST", "/api/v1/ingredients/restore"),
    ("POST", "/api/v1/permission/"),
    ("POST", "/api/v1/permission/sync-from-payload"),
    ("POST", "/api/v1/permission/sync-from-source"),
    ("POST", "/api/v1/recipes/"),
    ("POST", "/api/v1/recipes/restore"),
    ("POST", "/api/v1/recipes/{recipe_id}/gallery-images"),
    ("POST", "/api/v1/recipes/{recipe_id}/images/generate-upload-policy"),
    ("POST", "/api/v1/recipes/{recipe_id}/steps/{step_id}/images"),
    ("POST", "/api/v1/role/"),
    ("POST", "/api/v1/role/merge"),
    ("POST", "/api/v1/role/restore"),
    ("POST", "/api/v1/tags/"),
    ("POST", "/api/v1/tags/merge"),
    ("POST", "/api/v1/tags/restore"),
    ("POST", "/api/v1/units/"),
    ("POST", "/api/v1/units/merge"),
    ("POST", "/api/v1/units/restore"),
    ("POST", "/api/v1/user/"),
    ("POST", "/api/v1/user/restore"),
    ("POST", "/api/v1/user/me/avatar/generate-credential"),
    ("POST", "/api/v1/user/{user_id}/avatar/generate-upload-policy"),
    ("PUT", "/api/v1/categories/{category_id}"),
    ("PUT", "/api/v1/file_management/{record_id}"),
    ("PUT", "/api/v1/ingredients/{ingredient_id}"),
    ("PUT", "/api/v1/permission/{permission_id}"),
    ("PUT", "/api/v1/recipes/{recipe_id}"),
    ("PUT", "/api/v1/recipes/{recipe_id}/cover-image"),
    ("PUT", "/api/v1/role/{role_id}"),
    ("PUT", "/api/v1/tags/{tag_id}"),
    ("PUT", "/api/v1/units/{unit_id}"),
    ("PUT", "/api/v1/user/{user_id}"),
}

PUBLIC_OPENAPI_ENDPOINTS = {
    ("DELETE", "/api/v1/file/files"),
    ("DELETE", "/api/v1/file_management/bulk/permanent"),
    ("DELETE", "/api/v1/file_management/bulk/soft"),
    ("DELETE", "/api/v1/file_management/{record_id}"),
    ("DELETE", "/api/v1/file_management/{record_id}/permanent"),
    ("DELETE", "/api/v1/ingredients/"),
    ("DELETE", "/api/v1/ingredients/permanent-delete"),
    ("DELETE", "/api/v1/ingredients/{ingredient_id}"),
    ("DELETE", "/api/v1/tags/batch"),
    ("DELETE", "/api/v1/tags/permanent-delete"),
    ("DELETE", "/api/v1/tags/{tag_id}"),
    ("DELETE", "/api/v1/user/{user_id}"),
    ("GET", "/api/v1/auth/health"),
    ("GET", "/api/v1/file/files"),
    ("GET", "/api/v1/file/files/exists"),
    ("GET", "/api/v1/file/presigned-url/get"),
    ("GET", "/api/v1/file_management/"),
    ("GET", "/api/v1/file_management/stats"),
    ("GET", "/api/v1/file_management/{record_id}"),
    ("GET", "/api/v1/ingredients/"),
    ("GET", "/api/v1/tags/"),
    ("GET", "/api/v1/user/{user_id}"),
    ("POST", "/api/v1/auth/change-password"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh-token"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/reset-password"),
    ("POST", "/api/v1/file/presigned-url/put"),
    ("POST", "/api/v1/file_management/merge"),
    ("POST", "/api/v1/file_management/restore/bulk"),
    ("POST", "/api/v1/file_management/{record_id}/restore"),
    ("POST", "/api/v1/ingredients/"),
    ("POST", "/api/v1/ingredients/merge"),
    ("POST", "/api/v1/ingredients/restore"),
    ("POST", "/api/v1/tags/"),
    ("POST", "/api/v1/tags/merge"),
    ("POST", "/api/v1/tags/restore"),
    ("POST", "/api/v1/user/"),
    ("PUT", "/api/v1/file_management/{record_id}"),
    ("PUT", "/api/v1/ingredients/{ingredient_id}"),
    ("PUT", "/api/v1/tags/{tag_id}"),
    ("PUT", "/api/v1/user/{user_id}"),
}


def registered_api_endpoints(app) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods or not path.startswith("/api/v1/"):
            continue
        for method in methods:
            if method not in {"HEAD", "OPTIONS"}:
                endpoints.add((method, path))
    return endpoints


def openapi_endpoints(schema: dict) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method in path_item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                endpoints.add((method.upper(), path))
    return endpoints


def public_openapi_endpoints(schema: dict) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in path_item.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not operation.get("security"):
                endpoints.add((method.upper(), path))
    return endpoints


def test_registered_api_endpoint_inventory_is_explicit(app):
    assert registered_api_endpoints(app) == EXPECTED_API_ENDPOINTS


def test_openapi_endpoint_inventory_matches_registered_routes(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert openapi_endpoints(response.json()) == EXPECTED_API_ENDPOINTS


def test_public_openapi_endpoint_inventory_is_explicit(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert public_openapi_endpoints(response.json()) == PUBLIC_OPENAPI_ENDPOINTS
