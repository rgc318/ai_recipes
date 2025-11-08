# in app/core/utils/url_builder.py

from typing import Optional
from app.config import settings
from app.config.config_settings.config_schema import StorageCapabilities
from app.core.logger import logger  # It's good practice to log potential config errors


def build_public_storage_url(
    object_name: str,
    cdn_base_url: Optional[str],
    public_base_url: Optional[str], # 来自 S3Params.public_endpoint
    internal_base_url: Optional[str], # 来自 S3Params.endpoint
    bucket_name: str,
    capabilities: StorageCapabilities
) -> Optional[str]:
    """
    一个真正的“纯”工具函数，用于根据传入的上下文构建公共 URL。

    它不再读取任何全局设置，只依赖于传入的参数。

    URL 生成逻辑:
    1. 【CDN】如果配置了 cdn_base_url 且 capabilities 允许，优先使用。
    2. 【公网 Endpoint】如果配置了 public_base_url，根据 path_style 使用。
    3. 【内网 Endpoint】作为最后的回退，根据 path_style 使用。
    """
    if not object_name:
        return None

    try:
        # --- 优先级 1: CDN ---
        if capabilities.supports_cdn_rewrite and cdn_base_url:
            # CDN URL 总是 "path" 风格 (e.g., cdn.com/object_name)
            return f"{cdn_base_url.rstrip('/')}/{object_name.lstrip('/')}"

        # --- 优先级 2: 公网 Endpoint (public_base_url) ---
        if public_base_url:
            base_url = public_base_url.rstrip('/')
            if capabilities.path_style == "path":
                # Path 风格: e.g., https://r2.rgcdev.top/my-bucket/file.jpg
                return f"{base_url}/{bucket_name}/{object_name.lstrip('/')}"
            else:
                # Virtual 风格: e.g., https://my-bucket.s3.amazonaws.com/file.jpg
                # 假设 public_base_url 已经是 "https://bucket.domain.com"
                return f"{base_url}/{object_name.lstrip('/')}"

        # --- 优先级 3: 回退到内网 Endpoint (internal_base_url) ---
        # 警告：这可能会暴露内网地址，但这是原始逻辑的“智能”版本
        if internal_base_url:
            logger.warning(
                f"Building public URL for {object_name} using internal endpoint. "
                f"Consider setting 'public_endpoint' for this client."
            )
            base_url = internal_base_url.rstrip('/')
            if capabilities.path_style == "path":
                return f"{base_url}/{bucket_name}/{object_name.lstrip('/')}"
            else:
                return f"{base_url}/{object_name.lstrip('/')}"

        # --- ✅ 【【【 核心修复：优先级 4 】】】 ---
        # 如果 cdn_base_url, public_base_url 和 internal_base_url 都是 None,
        # 我们假定这是标准的 AWS S3 客户端，它需要一个 virtual-hosted URL。
        # (我们不再需要那个 "s3.amazonaws.com" in ... 的检查)
        logger.debug(f"Building default AWS S3 URL for {object_name}")
        return f"https://{bucket_name}.s3.amazonaws.com/{object_name.lstrip('/')}"


        # logger.error(f"Could not build public URL for {object_name}: No valid base URL found.")
        # return None

    except Exception as e:
        logger.error(f"Error in build_public_storage_url: {e}")
        return None


# def build_presigned_base_url(profile_name: str = 'public_cloud_storage') -> Optional[str]:
#     """
#     A utility function to get the correct *base URL* for generating presigned URLs.
#
#     This URL is the endpoint that the *client* (e.g., browser) will use to
#     execute the S3 API operation (e.g., PUT, POST, GET).
#
#     The priority is:
#     1. If 'public_endpoint' is set, use it (e.g., 'https://img.rgcdev.top').
#        This is the standard for services behind a reverse proxy.
#     2. If not, fall back to the main 'endpoint' (e.g., 'http://192.168.31.229:19000').
#        This is common for development or services exposed directly.
#
#     'cdn_base_url' is (and should be) intentionally ignored, as presigned
#     operations must target the S3 API origin, not a cache.
#     """
#     try:
#         # Get the config for the specified storage profile
#         client_params = settings.storage_clients[profile_name].params
#
#         # Determine protocol (this applies to both public and internal endpoints)
#         protocol = "https" if client_params.secure else "http"
#
#         # --- Priority 1: Use Public Endpoint (The main use case) ---
#         if client_params.public_endpoint:
#             # public_endpoint should just be the hostname, e.g., 'img.rgcdev.top'
#             # We strip any trailing slashes just in case
#             return f"{protocol}://{client_params.public_endpoint.rstrip('/')}"
#
#         # --- Priority 2: Fallback to the direct endpoint ---
#         # This is the same URL the backend uses for its internal connection.
#         return f"{protocol}://{client_params.endpoint.rstrip('/')}"
#
#     except (KeyError, AttributeError) as e:
#         logger.error(f"Could not build presigned base URL for profile '{profile_name}' due to config error: {e}")
#         return None
