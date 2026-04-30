# Integration Tests

Integration tests should verify behavior against real infrastructure such as PostgreSQL, Redis, and MinIO.

Keep these tests opt-in with the `integration` marker until the project has a dedicated test database and storage isolation strategy.

Authentication helpers:

- `integration_client`: session-scoped `TestClient` with application lifespan enabled.
- `integration_auth_state`: logs in once per test session using `TEST_AUTH_USERNAME` and `TEST_AUTH_PASSWORD`.
- `integration_authenticated_client`: shared client with the cached bearer token applied.
