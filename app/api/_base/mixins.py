# from collections.abc import Callable
# from logging import Logger
#
# import sqlalchemy.exc
# from fastapi import HTTPException, status
# from pydantic import UUID4, BaseModel
#
# from app.repos.repository_generic import RepositoryGeneric
# from app.schema.response import ErrorResponse
#
#
# class HttpRepo[C: BaseModel, R: BaseModel, U: BaseModel]:
#     """
#     The HttpRepo[C, R, U] class is a mixin class that provides a common set of methods for CRUD operations.
#     This class is intended to be used in a composition pattern where a class has a mixin property. For example:
#
#     ```
#     class MyClass:
#         def __init__(self, repo, logger):
#             self.mixins = HttpRepo(repo, logger)
#     ```
#
#     """
#
#     repo: RepositoryGeneric
#     exception_msgs: Callable[[type[Exception]], str] | None
#     default_message: str = "An unexpected error occurred."
#
#     def __init__(
#         self,
#         repo: RepositoryGeneric,
#         logger: Logger,
#         exception_msgs: Callable[[type[Exception]], str] | None = None,
#         default_message: str | None = None,
#     ) -> None:
#         self.repo = repo
#         self.logger = logger
#         self.exception_msgs = exception_msgs
#
#         if default_message:
#             self.default_message = default_message
#
#     def get_exception_message(self, ext: Exception) -> str:
#         if self.exception_msgs:
#             return self.exception_msgs(type(ext))
#         return self.default_message
#
#     def handle_exception(self, ex: Exception) -> None:
#         # Cleanup
#         self.logger.exception(ex)
#         self.repo.session.rollback()
#
#         # Respond
#         msg = self.get_exception_message(ex)
#
#         if isinstance(ex, sqlalchemy.exc.NoResultFound):
#             raise HTTPException(
#                 status.HTTP_404_NOT_FOUND,
#                 detail=ErrorResponse.respond(message=msg, exception=str(ex)),
#             )
#         else:
#             raise HTTPException(
#                 status.HTTP_400_BAD_REQUEST,
#                 detail=ErrorResponse.respond(message=msg, exception=str(ex)),
#             )
#
#     def create_one(self, data: C) -> R | None:
#         item: R | None = None
#         try:
#             item = self.repo.create(data)
#         except Exception as ex:
#             self.handle_exception(ex)
#
#         return item
#
#     def get_one(self, item_id: int | str | UUID4, key: str | None = None) -> R:
#         item = self.repo.get_one(item_id, key)
#
#         if not item:
#             raise HTTPException(
#                 status.HTTP_404_NOT_FOUND,
#                 detail=ErrorResponse.respond(message="Not found."),
#             )
#
#         return item
#
#     def update_one(self, data: U, item_id: int | str | UUID4) -> R:
#         item = self.repo.get_one(item_id)
#
#         if not item:
#             raise HTTPException(
#                 status.HTTP_404_NOT_FOUND,
#                 detail=ErrorResponse.respond(message="Not found."),
#             )
#
#         try:
#             item = self.repo.update(item_id, data)  # type: ignore
#         except Exception as ex:
#             self.handle_exception(ex)
#
#         return item
#
#     def patch_one(self, data: U, item_id: int | str | UUID4) -> R:
#         item = self.repo.get_one(item_id)
#
#         if not item:
#             raise HTTPException(
#                 status.HTTP_404_NOT_FOUND,
#                 detail=ErrorResponse.respond(message="Not found."),
#             )
#
#         try:
#             item = self.repo.patch(item_id, data.model_dump(exclude_unset=True, exclude_defaults=True))
#         except Exception as ex:
#             self.handle_exception(ex)
#
#         return item
#
#     def delete_one(self, item_id: int | str | UUID4) -> R | None:
#         item: R | None = None
#         try:
#             item = self.repo.delete(item_id)
#             self.logger.info(f"Deleting item with id {item_id}")
#         except Exception as ex:
#             self.handle_exception(ex)
#
#         return item
