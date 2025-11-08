import json
from abc import ABC
from typing import BinaryIO, List, Dict, Optional, Any
from urllib.parse import urlparse, urlunparse

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
        self.capabilities = self.s3_conf.capabilities  # <-- 【修改】直接获取 capabilities 对象
        self.endpoint_url = self._get_base_url()
        self.bucket_name = self.s3_conf.bucket_name
        self.public_base_url = self._get_public_base_url()

        # 【修改】我们不再从 s3_conf 直接读取 cdn_base_url，
        # 因为它应该由 build_final_url 结合 capabilities 智能处理
        # self.cdn_base_url = self.s3_conf.cdn_base_url or self.endpoint_url

        # 【修改】根据 StorageCapabilities 智能设置 BotoConfig
        # 1. 翻译寻址风格 (Path Style)
        # Boto3 接受: 'auto' (None), 'path', 'virtual'
        addressing_style = self.capabilities.path_style
        if addressing_style == 'auto':
            addressing_style = None  # Boto3 的 'auto' 对应的是 None

        # 2. 翻译签名版本
        # Pydantic: "v4" -> Boto3: "s3v4"
        # Pydantic: "v2" -> Boto3: "s3" (legacy)
        signature_version_map = {"v4": "s3v4", "v2": "s3"}
        signature_version = signature_version_map.get(self.capabilities.signature_version, "s3v4")

        client_config = BotoConfig(
            signature_version=signature_version,
            s3={'addressing_style': addressing_style},
            connect_timeout=self.s3_conf.connect_timeout,
            read_timeout=self.s3_conf.read_timeout
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.s3_conf.access_key,
            aws_secret_access_key=self.s3_conf.secret_key,
            config=client_config,  # 传入增强的 BotoConfig
            region_name=self.s3_conf.region
        )

        # 【修改】仅在 capabilities 允许时才尝试创建 Bucket
        if self.capabilities.supports_bucket_creation:
            self.create_bucket_if_not_exists(self.bucket_name)
        else:
            logger.debug(
                f"[S3 Driver] Skipping bucket check/creation for '{self.bucket_name}' (disabled by capabilities).")

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
        """
        构建最终可访问的 URL (可能是 CDN URL)
        【修改】将 client 的所有上下文传递给 URL 构建器
        """
        # 【修改】将 S3Client 实例所拥有的所有上下文传递给 utility 函数
        return build_public_storage_url(
            object_name=object_name,
            cdn_base_url=self.s3_conf.cdn_base_url,
            public_base_url=self.public_base_url,  # 来自 S3Params.public_endpoint
            internal_base_url=self.endpoint_url,  # 【新增】来自 S3Params.endpoint
            bucket_name=self.bucket_name,
            capabilities=self.capabilities  # 传递完整的 capabilities
        )

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

        if self.capabilities.supports_acl and final_acl:
            extra_args["ACL"] = final_acl
            logger.debug(f"[S3 Driver] Applying ACL '{final_acl}' for {object_name}.")
        else:
            logger.debug(f"[S3 Driver] No ACL will be applied for {object_name} (not supported or not configured).")

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

            if self.capabilities.supports_acl and final_acl:
                params["ACL"] = final_acl
                logger.debug(f"[S3 Driver] Applying ACL '{final_acl}' for copied object {destination_key}.")
            else:
                logger.debug(
                    f"[S3 Driver] No ACL will be applied for copy to {destination_key} (not supported or not configured).")

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
        """
        底层生成预签名 URL 的方法 (用于 GET 或 PUT)。
        会智能地将 Boto3 生成的 URL 替换为 public_endpoint (自定义域)。
        """

        # 1. Boto3 使用后端 endpoint (内网或公网) 生成 URL
        presigned_url = self.s3.generate_presigned_url(
            ClientMethod=client_method,
            Params={"Bucket": self.bucket_name, "Key": object_name},
            ExpiresIn=expires_in
        )

        # 2. ✅ 【【【 核心修复：应用与 POST 相同的逻辑 】】】
        # 检查是否 *需要* (e.g., MinIO) 且 *能够* (有 public_base_url) 重写
        if (
            self.capabilities.rewrite_presigned_host
            and self.public_base_url
        ):
            logger.debug(f"[S3 Driver] Rewriting {client_method} URL host using public_endpoint.")
            try:
                original_parts = urlparse(presigned_url)  # e.g., http://192.168.1.10:9000/...
                public_parts = urlparse(self.public_base_url)  # e.g., https://img.rgcdev.top

                new_parts = (
                    public_parts.scheme,  # https
                    public_parts.netloc,  # img.rgcdev.top
                    original_parts.path,  # /public-assets-bucket/object-name
                    original_parts.params,
                    original_parts.query,  # ...?AWSAccessKeyId=...
                    original_parts.fragment
                )
                presigned_url = urlunparse(new_parts)

            except Exception as e:
                logger.error(f"[S3 Driver] Failed to parse and rewrite {client_method} URL: {e}")
                # 不抛出异常, 最坏情况是使用 boto3 的内网 URL

        # (如果 R2, rewrite_presigned_host=False, 这一步会被跳过, presigned_url 保持 boto3 原样)
        return presigned_url

    def generate_presigned_post_policy(
        self,
        object_name: str,
        expires_in: int,
        conditions: Optional[List[Any]] = None,
        fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成带安全策略的预签名POST，用于客户端上传。
        会智能地将 Boto3 生成的 URL 替换为 public_endpoint (自定义域)。
        """
        try:
            # 1. Boto3 使用后端 endpoint 生成 policy
            policy_data = self.s3.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires_in
            )

            # 2. 【修改】根据 capability 智能重写 POST URL
            # 只有在服务商支持(e.g. R2)且配置了 public_base_url 时才执行重写
            if self.capabilities.rewrite_presigned_host and self.public_base_url and 'url' in policy_data:
                logger.debug("[S3 Driver] Attempting to rewrite POST URL with public_base_url...")
                try:
                    original_parts = urlparse(policy_data['url'])
                    public_parts = urlparse(self.public_base_url)

                    # 构建新 URL：
                    #   - scheme (http/https) 来自 public_base_url
                    #   - netloc (域名)       来自 public_base_url
                    #   - path (路径, e.g., "/" 或 "/bucket-name/") 来自 Boto3 的 URL
                    new_parts = (
                        public_parts.scheme,  # e.g., "https"
                        public_parts.netloc,  # e.g., "r2.rgcdev.top"
                        original_parts.path,  # e.g., "/" (for R2) OR "/public-assets-bucket/" (for MinIO)
                        original_parts.params,
                        original_parts.query,
                        original_parts.fragment
                    )

                    policy_data['url'] = urlunparse(new_parts)
                    logger.debug(f"[S3 Driver] Rewrote POST URL to public_base_url: {policy_data['url']}")

                except Exception as e:
                    logger.error(f"[S3 Driver] Failed to parse and rewrite POST URL: {e}")
                    # 不抛出异常，只记录日志，最坏情况是使用 Boto3 生成的内网 URL

            logger.debug(f"[S3 Driver] Generated presigned POST policy for {object_name}.")
            return policy_data

        except ClientError as e:
            # 【修改】为 R2 提供更明确的错误信息
            # R2 不支持 POST，Boto3 会抛出 "InvalidRequest" 或类似错误
            if "not implemented" in str(e).lower() or "InvalidRequest" in str(e):
                logger.error(
                    f"Failed to generate POST policy. Does '{self.s3_conf.endpoint}' support POST policies? (e.g., R2 does not): {e}")
                raise NotImplementedError(
                    "This storage client does not support presigned POST policies (e.g., R2)."
                )

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
