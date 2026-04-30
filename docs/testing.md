# Testing

## Current Status

The project now has a layered test baseline that separates fast local checks from external-service integration checks.

Current verified results:

```text
ENV=test uv run --python /usr/bin/python3 pytest -q
108 passed, 120 deselected, 5 warnings

ENV=test uv run --python /usr/bin/python3 pytest -q -m integration
120 passed, 108 deselected, 6 warnings
```

Default `pytest` excludes integration tests via `pyproject.toml`:

```toml
addopts = "-m 'not integration'"
```

## Test Layout

| Directory | Purpose |
| --- | --- |
| `tests/unit/` | Pure helper and dependency tests with no external services |
| `tests/contract/` | API inventory, OpenAPI, route order, request validation, response contracts |
| `tests/security/` | Anonymous access, invalid token, and authorization regression tests |
| `tests/integration/` | Tests that use app lifespan and real PostgreSQL, Redis, and storage configuration |
| `tests/builders/` | Reusable test data builders |
| `tests/fixtures/` | Shared pytest fixture plugins |
| `tests/helpers/` | Test helper functions |
| `tests/manual/` | Ad hoc HTTP requests, not collected by pytest |

## Fast Test Baseline

Run the default baseline before committing most code changes:

```bash
ENV=test uv run --python /usr/bin/python3 pytest -q
```

The fast baseline currently covers:

- App construction, health endpoint, and OpenAPI generation.
- Route inventory for all registered `/api/v1` endpoints.
- Duplicate route and route-order regressions.
- OpenAPI `operationId` uniqueness.
- Auth request validation.
- Response envelope helpers.
- Permission dependency matrix.
- Invalid bearer token behavior.
- Anonymous access behavior for protected endpoints.

## Integration Tests

Integration tests are opt-in:

```bash
ENV=test uv run --python /usr/bin/python3 pytest -q -m integration
```

They currently cover:

- Login state caching with `integration_auth_state`.
- Login, wrong password, refresh token, refresh-token failure, and logout flows.
- Public endpoint smoke tests.
- Authenticated protected endpoint smoke tests.

Integration tests read credentials from environment variables:

```bash
TEST_AUTH_USERNAME=vben TEST_AUTH_PASSWORD=... pytest -m integration
```

For local development, these values can live in ignored `.env.test`. Do not commit real integration credentials.

## API Inventory

`tests/contract/test_endpoint_inventory.py` is an explicit inventory of every registered `/api/v1` endpoint and every endpoint that OpenAPI currently exposes without an auth scheme.

When adding, removing, renaming, or changing the public/protected status of an endpoint, update this inventory intentionally in the same change.

## Smoke Tests

The suite has two broad endpoint smoke layers:

- `tests/security/test_protected_endpoint_contracts.py`: sends anonymous requests to protected endpoints and asserts they reject access without `500`.
- `tests/contract/test_public_endpoint_smoke.py`: sends minimal requests to public endpoints in integration mode and asserts they do not return unhandled `500` errors.
- `tests/integration/test_authenticated_endpoint_smoke.py`: sends authenticated minimal requests to protected endpoints and asserts they do not fail with `401` or `500`.

These tests do not replace detailed business assertions. They are designed to catch routing, auth, validation, and unhandled exception regressions early.

## Known Limitations

- Integration tests currently use real external services and a real test account.
- Business CRUD coverage is not yet complete for recipes, tags, ingredients, units, categories, users, roles, permissions, and files.
- Test data isolation is still limited; future work should add isolated test DB/schema cleanup or transaction rollback.
- Project-owned warnings should be reduced over time. Existing warnings are currently tolerated.

## Recommended Next Improvements

- Add isolated data factories for users, roles, permissions, recipes, tags, ingredients, units, categories, and file records.
- Add focused CRUD behavior tests per module.
- Add interface-level permission matrix tests for regular user versus superuser.
- Add CI jobs for default tests and optional integration tests.
- Add coverage reporting with a realistic threshold.
