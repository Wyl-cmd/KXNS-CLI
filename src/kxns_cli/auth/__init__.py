"""Auth module stubs for kxns-cli (OAuth removed)."""

from typing import Any

KXNS_CODE_PLATFORM_ID = "kxns-cli"


class OAuthManager:
    """Stub OAuthManager - OAuth functionality has been removed."""

    def __init__(self, config: Any = None):
        pass

    def common_headers(self) -> dict[str, str]:
        return {}

    async def refreshing(self, runtime: Any):
        """No-op context manager."""
        yield

    def resolve_api_key(self, api_key: Any, oauth_config: Any = None) -> str:
        """Return the API key directly."""
        if hasattr(api_key, "get_secret_value"):
            return api_key.get_secret_value()
        return str(api_key) if api_key else ""


async def login_kxns_code(*args, **kwargs):
    """Stub - login functionality removed."""
    raise NotImplementedError("Login functionality has been removed. Please use --api-url, --api-key, and --api-model options.")


async def logout_kxns_code(*args, **kwargs):
    """Stub - logout functionality removed."""
    pass


def get_platform_by_id(platform_id: str) -> dict[str, Any]:
    """Stub - platform lookup removed."""
    return {}


def get_platform_name_for_provider(provider_type: str) -> str:
    """Get platform name for provider type."""
    return provider_type


def parse_managed_provider_key(key: str) -> tuple[str, str] | None:
    """Stub - managed provider key parsing removed."""
    return None


def is_managed_provider_key(key: str) -> bool:
    """Stub - managed provider key check removed."""
    return False


def refresh_managed_models(*args, **kwargs) -> list[str]:
    """Stub - managed model refresh removed."""
    return []
