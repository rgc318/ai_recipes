# Configuration Reference

Configuration is assembled in `app/config/config_settings/config_manager.py`.

Load order:

1. `.env`
2. `.env.<ENV>`
3. `app/config/<ENV>.yaml`

The YAML file contains `${VAR}` placeholders. Values are resolved from environment variables and then validated by `AppConfig`.

## Environment Selection

```bash
ENV=dev
ENV=test
```

If `ENV` is not set, the code defaults to `config`, which loads `app/config/config.yaml`.

## Required Environment Variables

| Variable | Purpose |
| --- | --- |
| `PORT` | Application port used by config and healthcheck |
| `LOG_LEVEL` | Server log level |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `DB_NAME` | PostgreSQL database |
| `LOG_ENABLE_FILE` | Enable file logging |
| `JWT_SECRET` | JWT signing secret |
| `TESTING_MODE` | Security testing mode flag |
| `REDIS_HOST` | Redis host |
| `REDIS_PORT` | Redis port |
| `REDIS_DB` | Redis DB index |
| `REDIS_PASSWORD` | Redis password |
| `MINIO_ACCESS_KEY` | Shared MinIO/S3 access key |
| `MINIO_SECRET` | Shared MinIO/S3 secret |
| `PRIVATE_STORAGE_ENDPOINT` | Private storage endpoint |
| `PRIVATE_STORAGE_BUCKET` | Private storage bucket |
| `PRIVATE_STORAGE_SECURE` | Private storage HTTPS flag |
| `PUBLIC_STORAGE_ENDPOINT` | Public storage endpoint |
| `PUBLIC_STORAGE_BUCKET` | Public storage bucket |
| `PUBLIC_STORAGE_SECURE` | Public storage HTTPS flag |
| `PUBLIC_STORAGE_SECURE_CDN` | Public endpoint HTTPS flag |
| `PUBLIC_STORAGE_PUBLIC_ENDPOINT` | Public/CDN endpoint |
| `R2_ACCESS_KEY` | Cloudflare R2 access key |
| `R2_SECRET_KEY` | Cloudflare R2 secret |
| `TEST_AUTH_USERNAME` | Optional integration-test login username |
| `TEST_AUTH_PASSWORD` | Optional integration-test login password |

Use `.env.example` as a non-secret template.

## Storage Clients

Configured clients in YAML:

- `private_minio`: private MinIO-compatible bucket.
- `public_cloud_storage`: public MinIO-compatible bucket with optional public endpoint rewrite.
- `r2_test_storage`: S3-compatible Cloudflare R2 profile.

Important capability flags:

- `upload_modes`: supported upload mechanisms, such as `put_url`, `post_policy`, `multipart`.
- `supports_acl`: must be `false` for R2.
- `path_style`: `path` for local MinIO, `virtual` for R2-style addressing.
- `rewrite_presigned_host`: useful for local MinIO behind a public endpoint.

## Storage Profiles

Business profiles map file operations to storage clients:

- `user_avatars`: avatar uploads, image MIME types, 5 MB max.
- `recipe_images`: recipe images, image MIME types, 5 MB max.
- `secure_reports`: private report files.
- `general_files`: broad file type support, 10 MB default max.

## Security Settings

The application validates JWT issuer, audience, token type, and user status in `app/core/security/security.py`.

Test-only auth overrides live in pytest fixtures. The application entrypoint does not globally bypass `get_current_user`.
