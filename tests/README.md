# Test Suite

The test suite is split by purpose:

- `unit/`: pure helper and serialization tests with no application dependencies.
- `contract/`: API shape, route registration, OpenAPI, and request validation contracts.
- `security/`: authentication and authorization regression tests.
- `integration/`: reserved for tests that touch PostgreSQL, Redis, MinIO, or full application lifespan.
- `manual/`: ad hoc HTTP requests for local manual checks; not collected by pytest.
- `builders/`: reusable test data builders.
- `fixtures/`: pytest fixture plugins shared across test layers.

Default `pytest` runs the fast baseline and does not require external services. Integration tests are excluded by default.

`contract/test_endpoint_inventory.py` keeps an explicit inventory of every registered `/api/v1` endpoint and every endpoint that OpenAPI currently exposes without an auth scheme. When a route is added, removed, renamed, or changes public/protected status, update that inventory intentionally in the same change.

Use markers for focused runs:

```bash
pytest -m unit
pytest -m contract
pytest -m security
pytest -m integration
```

Integration auth tests read credentials from environment variables:

```bash
TEST_AUTH_USERNAME=vben TEST_AUTH_PASSWORD=... pytest -m integration
```

The `integration_auth_state` fixture logs in once per pytest session and caches the access token plus refresh cookie on the shared integration client.
