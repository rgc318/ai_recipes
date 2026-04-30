# Architecture

AI Recipes is a FastAPI backend for recipe management, user administration, file storage, and AI-ready recipe workflows.

## Runtime Layers

- `app/main.py`: FastAPI application setup, middleware, exception handlers, router registration, and startup lifecycle.
- `app/api/routes`: HTTP route modules grouped by domain.
- `app/services`: Business orchestration and domain workflows.
- `app/repo`: Persistence helpers and repository factories.
- `app/models`: SQLModel database models.
- `app/schemas`: Request and response DTOs.
- `app/infra`: Infrastructure adapters for database, Redis, and storage.
- `app/config`: YAML + environment based configuration.

## Main Domains

- Auth: register, login, logout, refresh token, password operations.
- Users and RBAC: users, roles, permissions, permission sync.
- Recipes: recipes, tags, ingredients, units, categories.
- Files: uploads, presigned credentials, file records, storage management.

See domain-specific documents:

- [Authentication And Permissions](auth-and-permissions.md)
- [File Storage](storage.md)
- [Database](database.md)
- [API Overview](api.md)

## External Dependencies

- PostgreSQL with async SQLAlchemy and SQLModel.
- Redis for cache/session-style infrastructure.
- S3-compatible object storage, including MinIO and Cloudflare R2 style clients.

## Request Flow

1. FastAPI receives a request under `/api/v1`.
2. Route dependencies resolve the current user, permissions, and services.
3. Service layer executes business rules.
4. Repository/storage clients persist data or object files.
5. Routes return the standard response envelope where applicable.

## Known Technical Debt

- Some admin route dependencies are commented out or incomplete.
- Some OpenAPI-public endpoints still need security-design review.
- Integration tests currently depend on real external services and a real test account.
- Permission config currently contains five permission definitions in `PERMISSIONS_CONFIG`; startup sync reports that count.
- `app/main.py` logs all routes at import time, which makes test and startup output noisy.
