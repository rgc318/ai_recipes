# app/core/exceptions/__init__.py

from .base_exception import (
    BaseBusinessException,
    NotFoundException,
    AlreadyExistsException,
    ConcurrencyConflictException,
    FileException,
)
from .user_exceptions import (
    UserAlreadyExistsException,
    UserNotFoundException,
    UserLockedOutException,
    UserInactiveException,
    UserUpdateFailedException,
    UserDeleteFailedException,
)
from .auth_exceptions import (
    LoginFailedException,
    RegisterFailedException,
    InvalidCredentialsException,
    TokenExpiredException,
    TokenInvalidException,
)
from .jwt_exceptions import (
    UnauthorizedException,
    TokenRevokedException,
    TokenTypeMismatchException,
    InvalidTokenException,
    TokenExpiredException,
)

__all__ = [
    "BaseBusinessException",
    "NotFoundException",
    "AlreadyExistsException",
    "ConcurrencyConflictException",
    "FileException",

    "UserAlreadyExistsException",
    "UserNotFoundException",
    "UserLockedOutException",
    "UserInactiveException",
    "UserUpdateFailedException",
    "UserDeleteFailedException",

    "LoginFailedException",
    "RegisterFailedException",
    "InvalidCredentialsException",
    "TokenExpiredException",
    "TokenInvalidException",

    "UnauthorizedException",
    "TokenRevokedException",
    "TokenTypeMismatchException",
    "InvalidTokenException",
    "TokenExpiredException",
]
