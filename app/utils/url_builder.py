# in app/core/utils/url_builder.py

from typing import Optional
from app.config import settings
from app.core.logger import logger  # It's good practice to log potential config errors


def build_public_storage_url(object_name: Optional[str]) -> Optional[str]:
    """
    A pure utility function to build a public storage URL, incorporating all business logic.
    It only depends on the global settings config.

    The URL generation follows this priority:
    1. If a CDN base URL is configured, it will be used.
    2. If not, but a public-facing endpoint is configured, that will be used.
    3. As a fallback, the standard internal endpoint will be used.
    """
    if not object_name:
        return None

    try:
        # We are specifically building a URL for the 'public_cloud_storage' profile.
        # This could be parameterized in the future if needed.
        client_params = settings.storage_clients['public_cloud_storage'].params
        bucket_name = client_params.bucket_name

        # --- Priority 1: Use CDN if available ---
        # A CDN URL is the highest priority for public assets.
        if client_params.cdn_base_url:
            # Ensure no double slashes by stripping slashes from base and adding one
            return f"{client_params.cdn_base_url.rstrip('/')}/{object_name.lstrip('/')}"

        # Determine protocol for non-CDN URLs
        protocol = "https" if client_params.secure else "http"

        # --- Priority 2: Use Public Endpoint if available ---
        # This is for when the storage is behind a reverse proxy or has a different public URL.
        if client_params.public_endpoint:
            return f"{protocol}://{client_params.public_endpoint}/{bucket_name}/{object_name}"

        # --- Priority 3: Fallback to the direct endpoint ---
        # This is the direct connection URL to the storage service.
        return f"{protocol}://{client_params.endpoint}/{bucket_name}/{object_name}"

    except (KeyError, AttributeError) as e:
        # Handle cases where settings might be missing or misconfigured.
        logger.error(f"Could not build public storage URL due to configuration error: {e}")
        # In a production environment, you might return a default placeholder image URL.
        return None
