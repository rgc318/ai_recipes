# Testing

## Test Strategy

The test suite is organized as a layered foundation:

- Bootstrap tests: app construction, health endpoint, OpenAPI generation.
- Route contract tests: current routes exist, removed legacy routes stay removed.
- Response contract tests: basic HTTP response behavior.
- Security regression tests: current auth defects are tracked with `xfail`.

## Run Tests

```bash
ENV=test uv run --python /usr/bin/python3 pytest -q
```

Expected current result:

```text
7 passed, 3 xfailed
```

## Why Some Tests Are Xfailed

The xfailed tests document known defects without breaking the whole suite:

- `app.main` globally overrides `get_current_user` with a mock returning `None`.
- Some protected endpoints return `200` or `500` instead of `401/403` for anonymous requests.
- `POST /api/v1/permission/sync-from-source` is registered twice.

These should be converted to normal passing tests after the underlying code is fixed.

## Test Design Rules

- Do not add broad "example" tests that call fake paths.
- Prefer one test file per concern.
- Use route contract tests for API path stability.
- Use service tests for business rules.
- Use integration tests only when external dependencies are explicitly required.
- Keep fast tests independent of real DB/Redis lifecycles unless marked as integration.

## Next Test Improvements

- Add `tests/factories/` for users, roles, recipes, tags, and file records.
- Add isolated database fixtures with transaction rollback.
- Add mock storage adapters for file service tests.
- Add permission matrix tests for anonymous, verified user, admin, and superuser contexts.

## Current Test Files

| File | Scope |
| --- | --- |
| `tests/conftest.py` | Shared fixtures and route map helpers |
| `tests/test_app_bootstrap.py` | App construction, health endpoint, OpenAPI |
| `tests/test_route_contracts.py` | Route existence, legacy route removal, duplicate route detection |
| `tests/test_response_contracts.py` | Basic response behavior |
| `tests/test_security_regressions.py` | Authorization defects tracked with `xfail` |
