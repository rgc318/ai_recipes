# Deployment

## Container

The Docker image runs the FastAPI app through Gunicorn and Uvicorn workers:

```text
gunicorn -w ${GUNICORN_WORKERS} -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:8000
```

## Required Services

- PostgreSQL
- Redis
- MinIO or another S3-compatible object store

The current compose file expects an external Docker network:

```text
ai-recipes-shared-network
```

## Environment

Use an environment file based on `.env.example`. Do not commit real credentials.

For development:

```bash
ENV=dev
```

For test-like deployments:

```bash
ENV=test
```

## Health Check

The application health endpoint is:

```text
/api/v1/auth/health
```

The container healthcheck uses `healthcheck.py`, which defaults to the same path. It can be overridden with:

```bash
HEALTHCHECK_PATH=/api/v1/auth/health
```

## Operational Checks

```bash
curl http://127.0.0.1:8000/api/v1/auth/health
curl http://127.0.0.1:8000/docs
docker ps --filter name=ai-recipes
docker inspect --format '{{json .State.Health}}' ai-recipes-app
```

## Known Deployment Notes

- If the container is marked unhealthy while `/api/v1/auth/health` returns `200`, verify the healthcheck path.
- Startup connects to the database, initializes Redis clients, and synchronizes permissions from backend source configuration.
- On the inspected server, `ai-recipes-app` was reachable on port `8000` but previously reported unhealthy because the old healthcheck path returned `404`.
- The current `healthcheck.py` default path is `/api/v1/auth/health`.
