import pytest
from fastapi import HTTPException

from app.api.dependencies.permissions import (
    require_authenticated_user,
    require_login,
    require_permission,
    require_role,
    require_superuser,
    require_verified_user,
)
from tests.builders.user_context import build_user_context


def test_require_login_returns_current_user():
    user = build_user_context()

    assert require_login(user) is user


def test_require_superuser_allows_superuser():
    user = build_user_context(is_superuser=True)

    assert require_superuser(user) is user


def test_require_superuser_rejects_regular_user():
    user = build_user_context(is_superuser=False)

    with pytest.raises(HTTPException) as exc_info:
        require_superuser(user)

    assert exc_info.value.status_code == 403


def test_require_verified_user_allows_verified_user():
    user = build_user_context(is_verified=True)

    assert require_verified_user(user) is user


def test_require_verified_user_rejects_unverified_user():
    user = build_user_context(is_verified=False)

    with pytest.raises(HTTPException) as exc_info:
        require_verified_user(user)

    assert exc_info.value.status_code == 403


def test_require_authenticated_user_rejects_unverified_user():
    user = build_user_context(is_verified=False)

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_user(user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    user = build_user_context(roles=["manager"])

    assert await require_role("manager")(user) is user


@pytest.mark.asyncio
async def test_require_role_rejects_missing_role():
    user = build_user_context(roles=["user"])

    with pytest.raises(HTTPException) as exc_info:
        await require_role("manager")(user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_allows_superuser_without_matching_role():
    user = build_user_context(is_superuser=True, roles=["user"])

    assert await require_role("manager")(user) is user


@pytest.mark.asyncio
async def test_require_permission_allows_matching_permission():
    user = build_user_context(permissions=["recipe:create"])

    assert await require_permission("recipe:create")(user) is user


@pytest.mark.asyncio
async def test_require_permission_rejects_missing_permission():
    user = build_user_context(permissions=["recipe:read"])

    with pytest.raises(HTTPException) as exc_info:
        await require_permission("recipe:create")(user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_permission_allows_superuser_without_matching_permission():
    user = build_user_context(is_superuser=True, permissions=[])

    assert await require_permission("recipe:create")(user) is user
