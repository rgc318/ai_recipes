# app/core/minio_client.py
from uuid import uuid4
from typing import Optional
from fastapi import UploadFile
from botocore.client import Config as BotoConfig
import boto3
from app.config.settings import settings
from app.core.logger import logger


class MinioClient:
    def __init__(self):
        self.minio_conf = settings.minio
        self.endpoint_url = self._get_base_url()
        self.cdn_base_url = self.minio_conf.cdn_base_url or self.endpoint_url

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.minio_conf.access_key,
            aws_secret_access_key=self.minio_conf.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )

        self.create_bucket_if_not_exists(self.minio_conf.bucket_name)

    def _get_base_url(self) -> str:
        protocol = "https" if self.minio_conf.secure else "http"
        return f"{protocol}://{self.minio_conf.endpoint}"

    def upload_fileobj(
        self,
        file: UploadFile,
        folder: str = "uploads",
        object_name: Optional[str] = None,
    ) -> str:
        ext = file.filename.split(".")[-1]
        if not object_name:
            object_name = f"{uuid4().hex}.{ext}"

        key = f"{folder}/{object_name}"

        logger.info(f"[MinIO] Uploading file to {self.minio_conf.bucket_name}/{key}")

        self.s3.upload_fileobj(
            file.file,
            Bucket=self.minio_conf.bucket_name,
            Key=key,
            ExtraArgs={"ContentType": file.content_type},
        )

        return f"{self.cdn_base_url}/{self.minio_conf.bucket_name}/{key}"

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.minio_conf.bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_object(self, key: str):
        logger.info(f"[MinIO] Deleting object: {key}")
        self.s3.delete_object(Bucket=self.minio_conf.bucket_name, Key=key)

    def list_objects(self, prefix: str = "") -> list[str]:
        response = self.s3.list_objects_v2(Bucket=self.minio_conf.bucket_name, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]

    def create_bucket_if_not_exists(self, bucket_name: str):
        try:
            buckets = [b["Name"] for b in self.s3.list_buckets()["Buckets"]]
            if bucket_name not in buckets:
                self.s3.create_bucket(Bucket=bucket_name)
                logger.info(f"[MinIO] Created bucket: {bucket_name}")
            else:
                logger.debug(f"[MinIO] Bucket already exists: {bucket_name}")
        except Exception as e:
            logger.error(f"[MinIO] Failed to check or create bucket '{bucket_name}': {e}")

    def test_connection(self) -> bool:
        try:
            self.s3.list_buckets()
            return True
        except Exception as e:
            logger.error(f"[MinIO] Connection test failed: {e}")
            return False


# 单例对象
minio_client = MinioClient()
