from datetime import UTC, datetime
from uuid import UUID

from app.schemas.users.user_context import UserContext


def build_user_context(
    *,
    user_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
    username: str = "test-user",
    email: str = "test@example.com",
    is_superuser: bool = False,
    is_verified: bool = True,
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
) -> UserContext:
    return UserContext(
        id=user_id,
        username=username,
        email=email,
        phone=None,
        full_name="Test User",
        avatar=None,
        is_active=True,
        is_superuser=is_superuser,
        is_verified=is_verified,
        is_locked=False,
        is_deleted=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_login_at=None,
        roles=roles or (["superuser"] if is_superuser else ["user"]),
        permissions=permissions or [],
    )
