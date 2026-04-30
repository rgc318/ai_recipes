# AI Recipes Backend

FastAPI backend for recipe management, user/RBAC administration, file storage, and AI-ready recipe workflows.

## Features

- Auth: register, login, logout, refresh token, password operations.
- User management: users, roles, permissions, and permission synchronization.
- Recipe domain: recipes, tags, ingredients, units, and categories.
- File storage: uploads, file records, presigned upload/download flows, MinIO/S3/R2 style storage.
- Infrastructure: async PostgreSQL, Redis, object storage, Docker deployment.

## Tech Stack

- Python 3.12 or 3.13
- FastAPI
- SQLModel / SQLAlchemy asyncio
- PostgreSQL
- Redis
- S3-compatible object storage
- `uv`

## Quick Start

```bash
cp .env.example .env
cp .env.example .env.dev
uv sync --python /usr/bin/python3 --extra dev
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

## Configuration

Configuration is loaded from `.env`, `.env.<ENV>`, and `app/config/<ENV>.yaml`.

Real `.env` files are intentionally ignored by Git. Use `.env.example` as the template.

## Tests

```bash
ENV=test uv run --python /usr/bin/python3 pytest -q
```

Current baseline:

```text
7 passed, 3 xfailed
```

The xfailed tests record known auth and route-registration issues.

## Documentation

- [Architecture](docs/architecture.md)
- [API Overview](docs/api.md)
- [Configuration](docs/configuration.md)
- [Database](docs/database.md)
- [Authentication And Permissions](docs/auth-and-permissions.md)
- [File Storage](docs/storage.md)
- [Development](docs/development.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Operations Runbook](docs/operations.md)

## Important Notes

- Python 3.14 is excluded because current dependency builds are not reliable with it.
- The runtime health endpoint is `/api/v1/auth/health`.
- Do not commit real credentials.
