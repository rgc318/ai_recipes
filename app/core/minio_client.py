from uuid import uuid4
from fastapi import UploadFile
from botocore.client import Config as BotoConfig
import boto3
from app.config.settings import settings  # 使用你的统一配置系统
from app.core.logger import logger


class MinioClient:
    def __init__(self):
        self.minio_conf = settings.minio

        protocol = "https" if self.minio_conf.secure else "http"
        self.endpoint_url = f"{protocol}://{self.minio_conf.endpoint}"

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.minio_conf.access_key,
            aws_secret_access_key=self.minio_conf.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )

        # 启动时确保 bucket 存在
        self.create_bucket_if_not_exists(self.minio_conf.bucket_name)

    def upload_fileobj(self, file: UploadFile, folder: str = "images") -> str:
        ext = file.filename.split(".")[-1]
        object_name = f"{folder}/{uuid4().hex}.{ext}"

        logger.info(f"[MinIO] Uploading file to {self.minio_conf.bucket_name}/{object_name}")

        self.s3.upload_fileobj(
            file.file,
            Bucket=self.minio_conf.bucket_name,
            Key=object_name,
            ExtraArgs={"ContentType": file.content_type},
        )

        file_url = f"{self.endpoint_url}/{self.minio_conf.bucket_name}/{object_name}"
        return file_url

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
        except Exception:
            return False

# 单例对象
minio_client = MinioClient()
