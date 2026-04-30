# Database

The project uses SQLModel on top of SQLAlchemy asyncio, backed by PostgreSQL.

## Runtime Connection

The database URL is built from environment variables:

```text
postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
```

The local development environment has been verified with PostgreSQL on:

```text
192.168.31.229:54321
```

## Session Lifecycle

Database sessions are provided by `app/infra/db/session.py`.

Behavior:

- `get_session()` yields an `AsyncSession`.
- The session commits after a successful request.
- The session rolls back if an exception is raised.
- The session is always closed in `finally`.

## Startup Schema Creation

`app.main` calls `create_db_and_tables()` during application startup.

That function calls:

```python
SQLModel.metadata.create_all
```

This means the application can create missing tables at runtime. For production-grade schema management, prefer Alembic migrations and avoid relying on startup `create_all` as the primary migration mechanism.

## Alembic

Alembic is configured under `alembic/`.

Common commands:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic current
alembic history
```

The current `alembic/env.py` uses `BaseModel.metadata` as `target_metadata`.

## Main Tables

User and RBAC:

- `user`
- `role`
- `permission`
- `user_role`
- `role_permission`
- `user_auth`
- `user_login_log`
- `user_login_fail_log`
- `user_preference`
- `verification_code`
- `user_action_log`

Recipe domain:

- `recipe`
- `recipe_step`
- `recipe_ingredient`
- `ingredient`
- `unit`
- `tag`
- `recipe_tag_link`
- `category`
- `recipe_category_link`
- `recipe_gallery_link`
- `recipe_step_image_link`

Files:

- `file_record`

## Soft Delete And Uniqueness

Most domain models inherit shared base behavior for:

- UUID primary key
- timestamps
- audit fields
- soft delete fields
- active-record uniqueness constraints

Several unique constraints are scoped to non-deleted records using helper methods such as `soft_unique_index`.

## Testing Guidance

Fast unit and contract tests should not trigger the real application lifespan by default. Integration tests that touch PostgreSQL should be explicitly marked and should use:

- a separate test database,
- transaction rollback fixtures,
- isolated seed data,
- no dependency on existing production-like rows.
