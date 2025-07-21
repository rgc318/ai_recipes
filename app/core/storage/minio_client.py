import os
import json
from abc import ABC
from typing import BinaryIO, List, Dict
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
import boto3

from app.config.settings import settings
from app.core.logger import logger
from app.config.config_schema import MinioClientConfig
from app.core.storage.storage_interface import StorageClientInterface
from app.utils.url_builder import build_public_storage_url


class MinioClient(StorageClientInterface, ABC):
    def __init__(self, config: MinioClientConfig):
        self.minio_conf = config.params
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
        # if self.cdn_base_url and self.minio_conf.public_endpoint is None:
        #     return f"{self.cdn_base_url}/{object_name}"
        #
        # if self.minio_conf.public_endpoint:
        #     protocol = "https" if self.minio_conf.secure else "http"
        #     return f"{protocol}://{self.minio_conf.public_endpoint}/{self.bucket_name}/{object_name}"
        # return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"
        return build_public_storage_url(object_name)

    def put_object(self, object_name: str, data: BinaryIO, length: int, content_type: str, acl: str = "public-read"):
        """底层 put_object 方法"""
        logger.info(f"[MinIO Driver] Putting object: {object_name}")
        # 使用 upload_fileobj 更强大
        self.s3.upload_fileobj(
            Fileobj=data,
            Bucket=self.bucket_name,
            Key=object_name,
            ExtraArgs={
                "ContentType": content_type,
                "ACL": acl
            }
        )
        # upload_fileobj 不返回 ETag，所以可以返回空字典或固定值
        return {}

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
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            logger.debug(f"[MinIO] Bucket '{bucket_name}' already exists.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"[MinIO] Bucket '{bucket_name}' not found. Creating...")
                self.s3.create_bucket(Bucket=bucket_name)

                # (建议添加) 根据需要设置存储桶策略
                # 例如，如果需要桶内所有对象都可被匿名读取
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                try:
                    self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                    logger.info(f"[MinIO] Set public-read policy for bucket '{bucket_name}'.")
                except ClientError as policy_error:
                    logger.error(f"[MinIO] Failed to set bucket policy for '{bucket_name}': {policy_error}")
                    # 即使策略设置失败，桶也已创建，根据业务决定是否需要抛出异常

            else:
                logger.error(f"[MinIO] Error checking bucket: {e}")
                raise

    # 在 MinioClient 类中添加此方法
    def list_objects(self, prefix: str = "") -> List[Dict]:
        """
        列出存储桶中的对象。
        :param prefix: 对象前缀，用于过滤。
        :return: 对象信息列表。
        """
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            object_list = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        object_list.append({
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"],
                            "etag": obj["ETag"]
                        })
            logger.info(f"[MinIO Driver] Listed {len(object_list)} objects with prefix '{prefix}'.")
            return object_list
        except ClientError as e:
            logger.error(f"[MinIO] Error listing objects with prefix '{prefix}': {e}")
            return []