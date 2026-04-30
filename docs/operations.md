# Operations Runbook

This runbook covers local and server-side checks for the current AI Recipes backend.

## Verified Service Endpoints

The current environment has been verified with:

| Service | Endpoint |
| --- | --- |
| Backend container | `192.168.31.229:8000` |
| Local dev backend | `127.0.0.1:8001` |
| Frontend container | `192.168.31.229:18088` |
| PostgreSQL | `192.168.31.229:54321` |
| Redis | `192.168.31.229:26739` |
| MinIO API | `192.168.31.229:19000` |
| MinIO Console | `192.168.31.229:19001` |

## Start Local Dev Server

```bash
ENV=dev uv run --python /usr/bin/python3 uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Use `8001` when `8000` is already used by the deployed container.

## Health Checks

Application:

```bash
curl http://127.0.0.1:8001/api/v1/auth/health
curl http://192.168.31.229:8000/api/v1/auth/health
```

Container healthcheck:

```bash
PORT=8001 python healthcheck.py
HEALTHCHECK_PATH=/api/v1/auth/health PORT=8000 python healthcheck.py
```

## Server Inspection

SSH:

```bash
ssh vivy@192.168.31.229
```

Containers:

```bash
docker ps --filter name=ai-recipes
docker inspect --format '{{json .State.Health}}' ai-recipes-app
docker logs --tail 200 ai-recipes-app
```

Ports:

```bash
ss -ltnp | grep -E ':8000|:54321|:26739|:19000|:19001'
```

## Common Problems

### Container Is Unhealthy But API Works

Check the healthcheck path. The correct endpoint is:

```text
/api/v1/auth/health
```

The project healthcheck script now defaults to that path.

### App Fails With `${PORT}` Or `${REDIS_PORT}` Validation Errors

The environment file was not loaded or is incomplete.

Check:

```bash
ls -la .env .env.dev .env.test
ENV=dev uv run --python /usr/bin/python3 python -c "from app.config.settings import settings; print(settings.server.port)"
```

### `uv` Selects Python 3.14

Use Python 3.12 explicitly:

```bash
uv sync --python /usr/bin/python3 --extra dev
ENV=test uv run --python /usr/bin/python3 pytest -q
```

The project requires `>=3.12,<3.14`.

### Tests Fail On Auth Expectations

Current auth behavior has known defects:

- `get_current_user` is globally overridden in `app/main.py`.
- Some protected endpoints return incorrect status codes.

See `docs/auth-and-permissions.md`.

### Route And OpenAPI Drift

Route inventory, duplicate route detection, route order, and OpenAPI operation ID uniqueness are covered by contract tests.

If an endpoint is intentionally added, removed, renamed, or changes public/protected status, update `tests/contract/test_endpoint_inventory.py` in the same change.

## Logs

The application uses Loguru and can write file logs when `LOG_ENABLE_FILE=true`.

Docker logs:

```bash
docker logs --tail 200 ai-recipes-app
```

Local development logs are emitted to stdout and may also go to the configured `logs/` directory.
