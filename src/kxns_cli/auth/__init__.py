"""auth 模块入口（OPEN-8：删除双份 stub，统一 re-export 真实现）。

旧版在此处定义了与 auth/oauth.py、auth/platforms.py 重复的 stub，
导致 `from kxns_cli.auth import X` 与 `from kxns_cli.auth.oauth import X`
拿到不同对象（`is` 比较为 False），易引发隐蔽 AttributeError。

现在改为 re-export 真实现，保证无论从哪个路径导入都拿到同一对象。
"""

from __future__ import annotations

from kxns_cli.auth.oauth import (
    KXNS_CODE_PLATFORM_ID,
    OAuthEvent,
    OAuthEventKind,
    OAuthManager,
    login_kxns_code,
    logout_kxns_code,
)
from kxns_cli.auth.platforms import (
    MANAGED_PROVIDER_PREFIX,
    PLATFORMS,
    ModelInfo,
    Platform,
    get_platform_by_id,
    get_platform_by_name,
    get_platform_name_for_provider,
    is_managed_provider_key,
    list_models,
    lookup_model_info,
    managed_model_key,
    managed_provider_key,
    parse_managed_provider_key,
    refresh_managed_models,
)

__all__ = [
    # oauth
    "KXNS_CODE_PLATFORM_ID",
    "OAuthEvent",
    "OAuthEventKind",
    "OAuthManager",
    "login_kxns_code",
    "logout_kxns_code",
    # platforms
    "MANAGED_PROVIDER_PREFIX",
    "PLATFORMS",
    "ModelInfo",
    "Platform",
    "get_platform_by_id",
    "get_platform_by_name",
    "get_platform_name_for_provider",
    "is_managed_provider_key",
    "list_models",
    "lookup_model_info",
    "managed_model_key",
    "managed_provider_key",
    "parse_managed_provider_key",
    "refresh_managed_models",
]
