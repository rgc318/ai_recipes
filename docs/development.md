# Development

## Prerequisites

- Python 3.12 or 3.13. Python 3.14 is intentionally excluded.
- `uv`
- Reachable PostgreSQL, Redis, and object storage endpoints.

## Setup

```bash
cp .env.example .env
cp .env.example .env.dev
```

Edit `.env` and `.env.dev` with local service credentials.

Install runtime and development dependencies:

```bash
uv sync --python /usr/bin/python3 --extra dev
```

## Run Locally

Port `8000` may already be used by a deployed container. Use `8001` for local development when needed:

```bash
ENV=dev uv run --python /usr/bin/python3 uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/api/v1/auth/health
```

API docs:

```text
http://127.0.0.1:8001/docs
```

## Configuration Model

The application loads:

1. `.env`
2. `.env.<ENV>`
3. `app/config/<ENV>.yaml`

YAML files contain `${VAR}` placeholders that are resolved from environment variables.

More detail: [Configuration Reference](configuration.md).

## Useful Commands

```bash
ENV=test uv run --python /usr/bin/python3 pytest -q
ENV=test uv run --python /usr/bin/python3 pytest -q -m integration
ENV=dev uv run --python /usr/bin/python3 python -c "from app.main import app; print(len(app.routes))"
```

Default tests exclude integration checks. Run `pytest -m integration` when you need to verify real login, Redis-backed token operations, app lifespan, and endpoint smoke tests against the configured external services.

## Local Services Used In This Environment

The current development environment has been verified against:

| Service | Endpoint |
| --- | --- |
| PostgreSQL | `192.168.31.229:54321` |
| Redis | `192.168.31.229:26739` |
| MinIO API | `192.168.31.229:19000` |
| MinIO Console | `192.168.31.229:19001` |
| Existing backend container | `192.168.31.229:8000` |
| Existing frontend container | `192.168.31.229:18088` |

If `8000` is already in use locally, run the development server on `8001`.
