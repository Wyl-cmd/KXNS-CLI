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
