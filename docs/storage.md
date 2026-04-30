# File Storage

The project uses a profile-driven file storage layer. Business code requests a storage profile, and the storage factory resolves the correct client and behavior.

## Main Components

- `app/infra/storage/storage_factory.py`: initializes and resolves storage clients.
- `app/infra/storage/s3_client.py`: MinIO/S3-compatible implementation.
- `app/services/file/file_service.py`: upload and presigned credential orchestration.
- `app/services/file/file_record_service.py`: file metadata and record lifecycle.
- `app/models/files/file_record.py`: persisted metadata for uploaded objects.

## Storage Clients

Configured clients:

- `private_minio`: private MinIO bucket.
- `public_cloud_storage`: public MinIO bucket, optionally rewritten to a public endpoint.
- `r2_test_storage`: Cloudflare R2-compatible profile.

Important capabilities:

- `upload_modes`: `put_url`, `post_policy`, `multipart`.
- `supports_acl`: R2 must be `false`; MinIO/S3 can support ACL.
- `path_style`: local MinIO normally uses `path`; R2 uses `virtual`.
- `rewrite_presigned_host`: used when a generated internal endpoint must be replaced with a public endpoint.

## Storage Profiles

Business profiles:

| Profile | Purpose | Default folder | Max size |
| --- | --- | --- | --- |
| `user_avatars` | User avatars | `avatars/{user_id}` | 5 MB |
| `recipe_images` | Recipe images | `recipes/{recipe_id}` | 5 MB |
| `secure_reports` | Private reports | `secure/reports/{year}` | 10 MB default |
| `general_files` | Generic files | `general/{year}/{month}` | 10 MB default |

Each profile also defines allowed MIME types and preferred presigned upload mode.

## Direct Upload Flow

Recommended browser/client flow:

1. Request a presigned credential:

   ```text
   POST /api/v1/file/presigned-url/generate
   ```

2. Upload directly to object storage with the returned credential.

3. Register the uploaded file in the database:

   ```text
   POST /api/v1/file/register
   ```

4. Link the file record to a business object, for example:

   - avatar link endpoint,
   - recipe cover image endpoint,
   - recipe gallery endpoint,
   - recipe step image endpoint.

## Server-Side Upload Flow

Routes such as:

```text
POST /api/v1/file/upload/avatar
POST /api/v1/file/upload/by_profile
```

upload through the API server. `FileService` validates:

- MIME type,
- file size,
- profile folder parameters,
- object storage upload result.

## File Record Model

`FileRecord` stores:

- `object_name`: object key in storage.
- `original_filename`
- `file_size`
- `content_type`
- `etag`
- `profile_name`
- `uploader_id`
- `is_associated`
- soft delete metadata inherited from the base model.

`object_name` is unique among active records.

## Lifecycle Operations

File management routes support:

- paginated records,
- metadata update,
- soft delete,
- restore,
- permanent delete,
- merge duplicate records,
- storage statistics.

Permanent delete should validate that the file is not still referenced by users or recipes.

## Operational Checks

```bash
curl http://192.168.31.229:19000
curl http://127.0.0.1:8001/api/v1/auth/health
```

For MinIO console access, use the configured console port, currently verified as:

```text
192.168.31.229:19001
```
