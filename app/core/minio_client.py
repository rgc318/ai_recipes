import os
import json
from uuid import uuid4
from typing import Optional, BinaryIO
from fastapi import UploadFile, HTTPException
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
import boto3

from app.config.settings import settings
from app.core.logger import logger


class MinioClient:
    def __init__(self):
        self.minio_conf = settings.minio
        self.endpoint_url = self._get_base_url()
        self.bucket_name = self.minio_conf.bucket_name

        self.cdn_base_url = self.minio_conf.cdn_base_url or self.endpoint_url
        self.cdn_prefix_mapping = self.minio_conf.cdn_prefix_mapping or {}

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.minio_conf.access_key,
            aws_secret_access_key=self.minio_conf.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )

        self.create_bucket_if_not_exists(self.bucket_name)

    def _get_base_url(self) -> str:
        protocol = "https" if self.minio_conf.secure else "http"
        return f"{protocol}://{self.minio_conf.endpoint}"

    def _build_key(self, folder: str, object_name: str) -> str:
        return f"{folder}/{object_name}".lstrip("/")

    def build_url(self, key: str, use_cdn: bool = True, custom_url = settings.minio.costume_url) -> str:
        if custom_url and self.minio_conf.cdn_base_url:
            return f"{self.cdn_base_url}/{self.bucket_name}/{key}"
        if use_cdn and self.minio_conf.cdn_base_url:
            for src_prefix, target_prefix in self.cdn_prefix_mapping.items():
                if key.startswith(src_prefix + "/"):
                    key = key.replace(src_prefix, target_prefix, 1)
                    break
            return f"{self.cdn_base_url}/{key}"
        return f"{self.endpoint_url}/{self.bucket_name}/{key}"

    def upload_fileobj(
        self,
        file: UploadFile,
        folder: str = "uploads",
        object_name: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> dict:
        ext = os.path.splitext(file.filename)[-1]
        if not object_name:
            object_name = f"{uuid4().hex}{ext}"

        key = self._build_key(folder, object_name)
        content_type = content_type or file.content_type

        logger.info(f"[MinIO] Uploading file to {self.bucket_name}/{key}")

        try:
            self.s3.upload_fileobj(
                Fileobj=file.file,
                Bucket=self.bucket_name,
                Key=key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ACL": "public-read", # 视项目需要开启
                },
            )
        except Exception as e:
            logger.exception(f"[MinIO] Upload failed for {key}: {e}")
            raise

        return {
            "url": self.build_url(key),
            "key": key,
            "content_type": content_type,
        }

    def upload_stream(
        self,
        stream: BinaryIO,
        content_type: str,
        folder: str = "uploads",
        object_name: Optional[str] = None,
    ) -> dict:
        if not object_name:
            object_name = f"{uuid4().hex}"
        key = self._build_key(folder, object_name)
        try:
            self.s3.upload_fileobj(
                Fileobj=stream,
                Bucket=self.bucket_name,
                Key=key,
                ExtraArgs={"ContentType": content_type},
            )
            return {
                "url": self.build_url(key),
                "key": key,
                "content_type": content_type,
            }
        except Exception as e:
            logger.error(f"[MinIO] Failed to upload stream: {e}")
            raise

    def generate_presigned_url(self, key: str, expires_in: int = 3600, use_cdn: bool = False) -> str:
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            if use_cdn and self.minio_conf.cdn_base_url:
                return self.build_url(key)
            return url
        except ClientError as e:
            logger.error(f"[MinIO] Failed to generate presigned URL for {key}: {e}")
            raise


    def generate_object_key(self, folder: str, filename: Optional[str] = None) -> str:
        """
        统一生成文件 key（路径）
        """
        ext = os.path.splitext(filename)[-1] if filename else ""
        object_name = f"{uuid4().hex}{ext}"
        return self._build_key(folder, object_name)

    def generate_presigned_put_url_with_final_url(
        self,
        folder: str = "uploads",
        filename: Optional[str] = None,
        expires_in: int = 3600
    ) -> dict:
        """
        生成预签名上传 URL，并返回 key + final_url
        """
        key = self.generate_object_key(folder, filename)

        try:
            put_url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            final_url = self.build_url(key)
            return {
                "put_url": put_url,
                "key": key,
                "final_url": final_url,
                "expires_in": expires_in,
                "url_type": "presigned_put"
            }
        except Exception as e:
            logger.error(f"[MinIO] Failed to generate presigned PUT URL for {key}: {e}")
            raise
    def generate_presigned_put_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            return self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as e:
            logger.error(f"[MinIO] Failed to generate presigned PUT URL: {e}")
            raise

    def delete_object(self, key: str):
        logger.info(f"[MinIO] Deleting object: {key}")

        # 检查文件是否存在
        if not self.object_exists(key):
            logger.warning(f"[MinIO] Object {key} does not exist, skipping deletion.")
            return  # 文件不存在，直接跳过删除操作

        try:
            # 删除文件
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"[MinIO] Object {key} deleted successfully.")
        except ClientError as e:
            # 处理不同的错误情况
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.warning(f"[MinIO] File {key} not found during deletion.")
            else:
                logger.error(f"[MinIO] Failed to delete object {key}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete object {key}: {e}")

    def list_objects(self, prefix: str = "") -> list[str]:
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            return [obj["Key"] for obj in response.get("Contents", [])]
        except ClientError as e:
            logger.error(f"[MinIO] List objects failed: {e}")
            return []

    def object_exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"[MinIO] head_object error: {e}")
            raise

    def create_bucket_if_not_exists(self, bucket_name: str):
        try:
            buckets = [b["Name"] for b in self.s3.list_buckets()["Buckets"]]
            if bucket_name not in buckets:
                self.s3.create_bucket(Bucket=bucket_name)
                logger.info(f"[MinIO] Created bucket: {bucket_name}")
                self.set_bucket_policy(bucket_name)
            else:
                logger.debug(f"[MinIO] Bucket already exists: {bucket_name}")
        except Exception as e:
            logger.error(f"[MinIO] Failed to check/create bucket '{bucket_name}': {e}")

    def set_bucket_policy(self, bucket_name: str, public_read: bool = True):
        try:
            if public_read:
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }]
                }
                self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                logger.info(f"[MinIO] Set public read policy for {bucket_name}")
        except Exception as e:
            logger.error(f"[MinIO] Failed to set bucket policy: {e}")

    def test_connection(self) -> bool:
        try:
            self.s3.list_buckets()
            return True
        except Exception as e:
            logger.error(f"[MinIO] Connection test failed: {e}")
            return False


minio_client = MinioClient()
