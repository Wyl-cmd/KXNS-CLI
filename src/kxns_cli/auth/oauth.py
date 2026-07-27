"""Auth module stubs for kxns-cli (OAuth removed).

OPEN-5: login_kxns_code / logout_kxns_code 改为 async generator，
使调用方的 `async for event in ...` 能正常消费，yield 一个 error 事件
提示用户改用 `/setup` 或 `kxns api`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

KXNS_CODE_PLATFORM_ID = "kxns-cli"

# 事件类型与 kimi-cli 对齐，方便调用方统一处理
OAuthEventKind = Literal["info", "error", "waiting", "verification_url", "success"]


@dataclass(slots=True, frozen=True)
class OAuthEvent:
    """OAuth 流程事件（对齐 kimi-cli），用于 login/logout 的 async generator yield。"""

    type: OAuthEventKind
    message: str
    data: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


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
    """Stub async generator - login functionality removed.

    OPEN-5: 改为 async generator（含 yield），使调用方 `async for event in ...`
    能正常消费。yield 一个 error 事件提示用户改用 /setup 或 kxns api。
    """
    yield OAuthEvent(
        type="error",
        message=(
            "KXNS Code 平台登录功能已移除。请使用 `/setup` 或 `kxns api` "
            "配置 API（--api-url, --api-key, --api-model）。"
        ),
    )


async def logout_kxns_code(*args, **kwargs):
    """Stub async generator - logout functionality removed.

    OPEN-5: 改为 async generator（含 yield），使调用方 `async for event in ...`
    能正常消费。yield 一个 info 事件提示用户。
    """
    yield OAuthEvent(
        type="info",
        message="KXNS Code 平台登录功能已移除，无需登出。",
    )
