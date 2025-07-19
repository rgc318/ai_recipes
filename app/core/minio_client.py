import os
import json
from typing import BinaryIO
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

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.minio_conf.access_key,
            aws_secret_access_key=self.minio_conf.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",  # 通常对于 MinIO 可以是任意值
        )
        self.create_bucket_if_not_exists(self.bucket_name)

    def _get_base_url(self) -> str:
        protocol = "https" if self.minio_conf.secure else "http"
        return f"{protocol}://{self.minio_conf.endpoint}"

    def build_final_url(self, object_name: str) -> str:
        """构建最终可访问的 URL (可能是 CDN URL)"""
        # 简化 URL 构建逻辑，CDN 逻辑也可以在这里处理
        if self.cdn_base_url and self.minio_conf.out_cdn_base_url is None:
            return f"{self.cdn_base_url}/{object_name}"
        # return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"
        return f"{self.minio_conf.out_cdn_base_url}/{self.bucket_name}/{object_name}"

    def put_object(self, object_name: str, data: BinaryIO, length: int, content_type: str):
        """底层 put_object 方法"""
        logger.info(f"[MinIO Driver] Putting object: {object_name}")
        return self.s3.put_object(
            Bucket=self.bucket_name,
            Key=object_name,
            Body=data,
            ContentLength=length,
            ContentType=content_type,
            ACL="public-read"  # 视项目需要设置
        )

    def remove_object(self, object_name: str):
        """底层 remove_object 方法"""
        logger.info(f"[MinIO Driver] Removing object: {object_name}")
        return self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)

    def stat_object(self, object_name: str):
        """底层 stat_object 方法 (用于检查存在性)"""
        return self.s3.head_object(Bucket=self.bucket_name, Key=object_name)

    def get_presigned_url(self, client_method: str, object_name: str, expires_in: int):
        """底层生成预签名 URL 的方法"""
        return self.s3.generate_presigned_url(
            ClientMethod=client_method,
            Params={"Bucket": self.bucket_name, "Key": object_name},
            ExpiresIn=expires_in
        )

    def create_bucket_if_not_exists(self, bucket_name: str):
        # 检查存储桶是否存在
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            logger.debug(f"[MinIO] Bucket '{bucket_name}' already exists.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"[MinIO] Bucket '{bucket_name}' not found. Creating...")
                self.s3.create_bucket(Bucket=bucket_name)
                # 可以在这里设置存储桶策略
            else:
                logger.error(f"[MinIO] Error checking bucket: {e}")
                raise


# 创建一个全局单例
minio_client = MinioClient()