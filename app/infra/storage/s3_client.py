import json
from abc import ABC
from typing import BinaryIO, List, Dict, Optional, Any
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
import boto3

from app.core.exceptions import FileException
from app.core.logger import logger
from app.config.config_settings.config_schema import S3ClientConfig
from app.infra.storage.storage_interface import StorageClientInterface
from app.utils.url_builder import build_public_storage_url


class S3CompatibleClient(StorageClientInterface, ABC):
    def __init__(self, config: S3ClientConfig):
        self.s3_conf = config.params
        self.endpoint_url = self._get_base_url()
        self.bucket_name = self.s3_conf.bucket_name
        self.cdn_base_url = self.s3_conf.cdn_base_url or self.endpoint_url
        self.public_base_url = self._get_public_base_url()

        # 【修改】创建功能更全的 BotoConfig
        addressing_style = 'path' if self.s3_conf.force_path_style else 'virtual'

        client_config = BotoConfig(
            signature_version="s3v4",
            s3={'addressing_style': addressing_style},
            connect_timeout=self.s3_conf.connect_timeout,
            read_timeout=self.s3_conf.read_timeout
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,  # (可能为 None, 适配 AWS S3)
            aws_access_key_id=self.s3_conf.access_key,
            aws_secret_access_key=self.s3_conf.secret_key,
            config=client_config,  # 传入增强的 BotoConfig
            region_name=self.s3_conf.region  # 传入配置的 Region
        )

        self.create_bucket_if_not_exists(self.bucket_name)

    def _get_base_url(self) -> Optional[str]:
        # 【修改】适配 s3_conf 并处理 endpoint 为 None 的情况 (AWS S3)
        if not self.s3_conf.endpoint:
            return None
        protocol = "https" if self.s3_conf.secure else "http"
        return f"{protocol}://{self.s3_conf.endpoint}"

    def _get_public_base_url(self) -> Optional[str]:
        # 【修改】适配 s3_conf 并处理 public_endpoint 为 None 的情况
        if not self.s3_conf.public_endpoint:
            return None
        protocol = "https" if self.s3_conf.secure_cdn else "http"
        return f"{protocol}://{self.s3_conf.public_endpoint}"

    def build_final_url(self, object_name: str) -> str:
        """构建最终可访问的 URL (可能是 CDN URL)"""
        # 简化 URL 构建逻辑，CDN 逻辑也可以在这里处理
        return build_public_storage_url(object_name)

    def put_object(self, object_name: str, data: BinaryIO, length: int, content_type: str, acl: str = "USE_CONFIG"):
        """底层 put_object 方法"""
        logger.info(f"[S3 Driver] Putting object: {object_name}")

        extra_args = {
            "ContentType": content_type
        }

        final_acl = None
        if acl != "USE_CONFIG":
            final_acl = acl
        else:
            final_acl = self.s3_conf.default_acl  # 从配置中读取

        if final_acl:
            extra_args["ACL"] = final_acl
            logger.debug(f"[S3 Driver] Applying ACL '{final_acl}' for {object_name}.")
        else:
            logger.debug(f"[S3 Driver] No ACL will be applied for {object_name} (config is None or R2).")

        # 使用 upload_fileobj 更强大
        self.s3.upload_fileobj(
            Fileobj=data,
            Bucket=self.bucket_name,
            Key=object_name,
            ExtraArgs=extra_args,
        )
        logger.info(f"[S3 Driver] Upload for {object_name} complete. Fetching metadata...")
        try:
            # head_object 会返回一个包含 ETag, ContentLength 等信息的字典
            response = self.s3.head_object(
                Bucket=self.bucket_name,
                Key=object_name
            )

            # boto3 返回的 ETag 带有双引号，我们需要移除它们
            etag = response.get('ETag')
            if etag:
                response['ETag'] = etag.strip('"')

            return response

        except ClientError as e:
            logger.error(f"[S3 Driver] Failed to fetch metadata for {object_name} after upload: {e}")
            raise FileException("File uploaded but failed to retrieve metadata.")

    def remove_object(self, object_name: str):
        """底层 remove_object 方法"""
        logger.info(f"[S3 Driver] Removing object: {object_name}")
        return self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)

    def copy_object(
            self,
            destination_key: str,
            source_key: str,
            acl: Optional[str] = "USE_CONFIG",
            metadata: Optional[Dict[str, str]] = None,
            preserve_metadata: bool = True,
    ) -> None:
        """
        在桶内复制对象，支持 ACL 与元数据控制。

        :param destination_key: 目标对象 Key
        :param source_key: 源对象 Key
        :param acl: 访问权限控制（默认 public-read）
        :param metadata: 覆盖元数据（如 {"ContentType": "image/png"}）
        :param preserve_metadata: 是否保留源对象的元数据（默认 True）
        """
        logger.info(
            f"[S3 Driver] Copying object "
            f"from '{source_key}' to '{destination_key}' in bucket '{self.bucket_name}'"
        )
        try:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}

            # 元数据策略
            metadata_directive = "COPY" if preserve_metadata else "REPLACE"

            # 构建请求参数
            params = {
                "CopySource": copy_source,
                "Bucket": self.bucket_name,
                "Key": destination_key,
                "MetadataDirective": metadata_directive,
            }

            # 如果提供了元数据，必须用 REPLACE 模式
            if metadata:
                params["Metadata"] = metadata
                params["MetadataDirective"] = "REPLACE"

            # ACL（注意 MinIO 部分环境可能不支持 ACL）
            final_acl = None
            if acl != "USE_CONFIG":
                final_acl = acl
            else:
                final_acl = self.s3_conf.default_acl  # 从配置中读取

            if final_acl:
                params["ACL"] = final_acl

            # 执行复制
            response = self.s3.copy_object(**params)

            logger.info(
                f"[S3 Driver] Successfully copied '{source_key}' "
                f"to '{destination_key}' (ETag={response.get('CopyObjectResult', {}).get('ETag')})"
            )
            return response

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"Failed to copy object from '{source_key}' to '{destination_key}' "
                f"(ErrorCode={error_code}): {e}"
            )
            raise FileException("Cloud storage copy operation failed.") from e

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

    def generate_presigned_post_policy(
        self,
        object_name: str,
        expires_in: int,
        conditions: Optional[List[Any]] = None,
        fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成带安全策略的预签名POST，用于客户端上传。
        会智能替换为公网地址。
        """
        try:
            # 1. Boto3 使用内网 endpoint 生成 policy
            policy_data = self.s3.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires_in
            )

            # 【修改】更安全的 URL 替换逻辑
            # 仅当配置了 public_endpoint 并且我们有一个 internal endpoint (self.endpoint_url)
            # 可供替换时，才执行替换。
            # 如果 endpoint_url 为 None (例如 AWS S3), Boto3 会自动生成正确的公网 URL，无需替换。
            if self.s3_conf.public_endpoint and self.endpoint_url and 'url' in policy_data:
                policy_data['url'] = policy_data['url'].replace(
                    self.endpoint_url, self.public_base_url
                )
                logger.debug(f"[S3 Driver] Replaced internal endpoint with public endpoint for POST policy.")
            elif not self.endpoint_url:
                logger.debug(f"[S3 Driver] Boto3 generated public URL for POST policy, no replacement needed.")

            logger.debug(f"[S3 Driver] Generated presigned POST policy for {object_name}: {policy_data}")
            return policy_data
        except ClientError as e:
            logger.error(f"Failed to generate presigned POST policy for {object_name}: {e}")
            raise FileException("Could not generate upload policy.")

    def create_bucket_if_not_exists(self, bucket_name: str):
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            logger.debug(f"[S3 Driver] Bucket '{bucket_name}' already exists.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"[S3 Driver] Bucket '{bucket_name}' not found. Creating...")

                try:
                    # 对于非 us-east-1 的 AWS S3，创建时必须指定区域
                    if self.s3_conf.region != "us-east-1" and not self.s3_conf.endpoint:
                        self.s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.s3_conf.region}
                        )
                    else:
                        # MinIO 或 us-east-1
                        self.s3.create_bucket(Bucket=bucket_name)
                    logger.info(f"[S3 Driver] Successfully created bucket '{bucket_name}'.")

                except ClientError as create_error:
                    logger.error(f"[S3 Driver] Failed to create bucket '{bucket_name}': {create_error}")
                    raise

                # (建议添加) 根据需要设置存储桶策略
                # 例如，如果需要桶内所有对象都可被匿名读取
                # policy = {
                #     "Version": "2012-10-17",
                #     "Statement": [
                #         {
                #             "Effect": "Allow",
                #             "Principal": "*",
                #             "Action": ["s3:GetObject"],
                #             "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                #         }
                #     ]
                # }
                # try:
                #     self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                #     logger.info(f"[S3 Driver] Set public-read policy for bucket '{bucket_name}'.")
                # except ClientError as policy_error:
                #     logger.error(f"[S3 Driver] Failed to set bucket policy for '{bucket_name}': {policy_error}")
                #     # 即使策略设置失败，桶也已创建，根据业务决定是否需要抛出异常

            else:
                logger.error(f"[S3 Driver] Error checking bucket: {e}")
                raise

    # 在 S3CompatibleClient 类中添加此方法
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
                            "etag": obj["ETag"].strip('"')
                        })
            logger.info(f"[S3 Driver] Listed {len(object_list)} objects with prefix '{prefix}'.")
            return object_list
        except ClientError as e:
            logger.error(f"[S3 Driver] Error listing objects with prefix '{prefix}': {e}")
            return []
