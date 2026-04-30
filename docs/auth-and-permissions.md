# Authentication And Permissions

## Authentication Model

The current app auth provider is `AuthMethod.app`, implemented through credentials-based login.

Primary endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/refresh-token`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/reset-password`

## Token Flow

Login returns:

- an access token in the response body,
- a refresh token in an HttpOnly cookie.

Refresh token flow:

1. Client calls `/api/v1/auth/refresh-token`.
2. Backend reads `refresh_token` from cookie.
3. Backend validates token type.
4. Backend revokes/rotates the previous refresh token.
5. Backend issues a new access token and refresh token.

Logout:

- Access token is decoded.
- Its `jti` is revoked in Redis for the remaining lifetime.
- The refresh cookie is deleted from the response.

## Current User Resolution

`app/core/security/security.py` resolves the current user by:

1. Reading bearer token with `OAuth2PasswordBearer`.
2. Decoding and validating JWT type.
3. Loading the user with roles.
4. Rejecting inactive or missing users.
5. Building a `UserContext` with roles and aggregated permissions.

## RBAC Model

Models:

- `User`
- `Role`
- `Permission`
- `UserRole`
- `RolePermission`

Relationships:

- A user can have many roles.
- A role can have many permissions.
- `User.permissions` aggregates permission codes across all assigned roles.

Permission sync source:

```text
app/config/permission_config/permissions_enum.py
```

At startup, the app synchronizes permissions from `PERMISSIONS_CONFIG`.

Current config contains five permission definitions:

- `dashboard:view`
- `management:user:list`
- `management:user:create`
- `management:user:update`
- `management:user:delete`

## Permission Dependencies

Common dependencies in `app/api/dependencies/permissions.py`:

- `require_login`
- `require_superuser`
- `require_verified_user`
- `require_authenticated_user`
- `require_role(...)`
- `require_permission(...)`

## Current Test Coverage

The test suite currently covers:

- Anonymous requests to protected endpoints.
- Invalid bearer token rejection.
- Authenticated protected endpoint smoke checks.
- Login, refresh token, and logout flows.
- Permission dependency matrix for login, superuser, verified user, role, and permission checks.

Test-only auth overrides live in pytest fixtures. `app/main.py` does not globally bypass `get_current_user`.

Remaining hardening work is to define and enforce a clear permission matrix for each route group at the interface level.

## Recommended Permission Matrix

| User type | Expected access |
| --- | --- |
| Anonymous | Public health/docs and public read endpoints only |
| Authenticated unverified user | Minimal account operations |
| Verified user | Recipe browsing and own profile/file operations |
| Admin | Domain management for recipes/taxonomy/files |
| Superuser | User, role, permission, destructive operations |
