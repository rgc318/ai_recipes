def test_openapi_operation_ids_are_unique(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200

    operation_ids: list[str] = []
    for path_item in response.json()["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operation_ids.append(operation["operationId"])

    assert len(operation_ids) == len(set(operation_ids))


def test_security_sensitive_routes_advertise_auth_scheme(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    assert paths["/api/v1/user/me"]["get"]["security"]
    assert paths["/api/v1/role/"]["get"]["security"]
    assert paths["/api/v1/permission/"]["get"]["security"]
