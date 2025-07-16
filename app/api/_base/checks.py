# from fastapi import HTTPException, status
#
# from app.schema.management.management import PrivateUser
#
#
# class OperationChecks:
#     """
#     OperationChecks class is a mixin class that can be used on routers to provide common permission
#     checks and raise the appropriate http error as necessary
#     """
#
#     management: PrivateUser
#
#     ForbiddenException = HTTPException(status.HTTP_403_FORBIDDEN)
#     UnauthorizedException = HTTPException(status.HTTP_401_UNAUTHORIZED)
#
#     def __init__(self, management: PrivateUser) -> None:
#         self.management = management
#
#     # =========================================
#     # User Permission Checks
#
#     def can_manage_household(self) -> bool:
#         if not self.management.can_manage_household:
#             raise self.ForbiddenException
#         return True
#
#     def can_manage(self) -> bool:
#         if not self.management.can_manage:
#             raise self.ForbiddenException
#         return True
#
#     def can_invite(self) -> bool:
#         if not self.management.can_invite:
#             raise self.ForbiddenException
#         return True
#
#     def can_organize(self) -> bool:
#         if not self.management.can_organize:
#             raise self.ForbiddenException
#         return True
