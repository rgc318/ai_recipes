# API Overview

Base prefix:

```text
/api/v1
```

Interactive documentation:

```text
/docs
/openapi.json
```

## Auth

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/auth/health` | Health check |
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/refresh-token` | Refresh access token |
| POST | `/api/v1/auth/change-password` | Change password |
| POST | `/api/v1/auth/reset-password` | Reset password |

## Recipes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/recipes/` | Paginated recipe list |
| POST | `/api/v1/recipes/` | Create recipe |
| GET | `/api/v1/recipes/{recipe_id}` | Recipe details |
| PUT | `/api/v1/recipes/{recipe_id}` | Update recipe |
| DELETE | `/api/v1/recipes/{recipe_id}` | Soft delete recipe |
| DELETE | `/api/v1/recipes/batch` | Batch soft delete |
| POST | `/api/v1/recipes/restore` | Batch restore |
| DELETE | `/api/v1/recipes/permanent-delete` | Batch permanent delete |
| PUT | `/api/v1/recipes/{recipe_id}/cover-image` | Replace cover image |
| POST | `/api/v1/recipes/{recipe_id}/gallery-images` | Add gallery images |
| DELETE | `/api/v1/recipes/{recipe_id}/gallery-images/{image_record_id}` | Remove gallery image |
| POST | `/api/v1/recipes/{recipe_id}/steps/{step_id}/images` | Add step images |
| DELETE | `/api/v1/recipes/{recipe_id}/steps/{step_id}/images/{image_record_id}` | Remove step image |
| POST | `/api/v1/recipes/{recipe_id}/images/generate-upload-policy` | Generate recipe image upload policy |

## Recipe Taxonomy

### Tags

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/tags/` | Paginated tags |
| POST | `/api/v1/tags/` | Create tag |
| PUT | `/api/v1/tags/{tag_id}` | Update tag |
| DELETE | `/api/v1/tags/{tag_id}` | Delete tag |
| DELETE | `/api/v1/tags/batch` | Batch delete |
| POST | `/api/v1/tags/restore` | Restore tags |
| DELETE | `/api/v1/tags/permanent-delete` | Permanent delete |
| POST | `/api/v1/tags/merge` | Merge tags |

### Ingredients

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/ingredients/` | Paginated ingredients |
| POST | `/api/v1/ingredients/` | Create ingredient |
| PUT | `/api/v1/ingredients/{ingredient_id}` | Update ingredient |
| DELETE | `/api/v1/ingredients/` | Batch soft delete |
| DELETE | `/api/v1/ingredients/{ingredient_id}` | Single soft delete |
| POST | `/api/v1/ingredients/restore` | Restore ingredients |
| DELETE | `/api/v1/ingredients/permanent-delete` | Permanent delete |
| POST | `/api/v1/ingredients/merge` | Merge ingredients |

### Units

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/units/all` | All units for selectors |
| GET | `/api/v1/units/` | Paginated units |
| POST | `/api/v1/units/` | Create unit |
| PUT | `/api/v1/units/{unit_id}` | Update unit |
| DELETE | `/api/v1/units/{unit_id}` | Delete unit |
| DELETE | `/api/v1/units/batch` | Batch delete |
| POST | `/api/v1/units/restore` | Restore units |
| DELETE | `/api/v1/units/permanent-delete` | Permanent delete |
| POST | `/api/v1/units/merge` | Merge units |

### Categories

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/categories/tree` | Category tree |
| GET | `/api/v1/categories/` | Paginated categories |
| POST | `/api/v1/categories/` | Create category |
| GET | `/api/v1/categories/{category_id}` | Category details |
| PUT | `/api/v1/categories/{category_id}` | Update category |
| DELETE | `/api/v1/categories/{category_id}` | Soft delete category |
| DELETE | `/api/v1/categories/batch` | Batch soft delete |
| POST | `/api/v1/categories/restore` | Restore categories |
| DELETE | `/api/v1/categories/permanent-delete` | Permanent delete |
| POST | `/api/v1/categories/merge` | Merge categories |

## Users And RBAC

### Users

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/user/me` | Current user context |
| PATCH | `/api/v1/user/me` | Update profile |
| PATCH | `/api/v1/user/me/password` | Change current user password |
| GET | `/api/v1/user/info` | Current user profile |
| PATCH | `/api/v1/user/me/avatar` | Upload avatar |
| POST | `/api/v1/user/me/avatar/generate-credential` | Avatar upload credential |
| PATCH | `/api/v1/user/me/avatar/link-uploaded-file` | Link uploaded avatar |
| GET | `/api/v1/user/` | Paginated users |
| POST | `/api/v1/user/` | Create user |
| GET | `/api/v1/user/{user_id}` | User details |
| PUT | `/api/v1/user/{user_id}` | Update user |
| DELETE | `/api/v1/user/{user_id}` | Soft delete user |
| DELETE | `/api/v1/user/batch` | Batch delete users |
| POST | `/api/v1/user/restore` | Restore users |
| DELETE | `/api/v1/user/permanent-deactivation` | Permanent deactivation/anonymization |

### Roles

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/role/selector` | Role selector list |
| GET | `/api/v1/role/` | Paginated roles |
| POST | `/api/v1/role/` | Create role |
| GET | `/api/v1/role/{role_id}` | Role details |
| PUT | `/api/v1/role/{role_id}` | Update role |
| DELETE | `/api/v1/role/` | Batch soft delete |
| POST | `/api/v1/role/restore` | Restore roles |
| DELETE | `/api/v1/role/permanent` | Permanent delete |
| POST | `/api/v1/role/merge` | Merge roles |

### Permissions

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/permission/selector` | Permission selector list |
| GET | `/api/v1/permission/` | Paginated permissions |
| POST | `/api/v1/permission/` | Create permission |
| GET | `/api/v1/permission/{permission_id}` | Permission details |
| PUT | `/api/v1/permission/{permission_id}` | Update permission |
| DELETE | `/api/v1/permission/{permission_id}` | Soft delete permission |
| POST | `/api/v1/permission/sync-from-source` | Sync permissions from backend config |
| POST | `/api/v1/permission/sync-from-payload` | Sync permissions from request body |
| DELETE | `/api/v1/permission/permanent` | Permanent delete |

Note: `POST /api/v1/permission/sync-from-source` is currently registered twice in code.

## Files

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/file/upload/avatar` | Upload avatar |
| POST | `/api/v1/file/upload/by_profile` | Upload by storage profile |
| GET | `/api/v1/file/files` | List files by profile |
| DELETE | `/api/v1/file/files` | Delete objects by profile |
| GET | `/api/v1/file/files/exists` | Object existence check |
| POST | `/api/v1/file/files/move` | Move object and update file record |
| GET | `/api/v1/file/presigned-url/get` | Generate download URL |
| POST | `/api/v1/file/presigned-url/generate` | Generate preferred upload credential |
| POST | `/api/v1/file/presigned-url/put` | Generate PUT upload URL |
| POST | `/api/v1/file/presigned-url/policy` | Generate POST upload policy |
| POST | `/api/v1/file/register` | Register uploaded file record |

## File Management

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/file_management/` | Paginated file records |
| GET | `/api/v1/file_management/{record_id}` | File record details |
| PUT | `/api/v1/file_management/{record_id}` | Update file metadata |
| DELETE | `/api/v1/file_management/{record_id}` | Soft delete file record |
| POST | `/api/v1/file_management/{record_id}/restore` | Restore file record |
| DELETE | `/api/v1/file_management/{record_id}/permanent` | Delete object and record permanently |
| POST | `/api/v1/file_management/restore/bulk` | Bulk restore |
| DELETE | `/api/v1/file_management/bulk/soft` | Bulk soft delete |
| DELETE | `/api/v1/file_management/bulk/permanent` | Bulk permanent delete |
| POST | `/api/v1/file_management/merge` | Merge duplicate records |
| GET | `/api/v1/file_management/stats` | Storage statistics |
