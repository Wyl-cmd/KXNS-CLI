from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Self

import tomlkit
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    field_serializer,
    model_validator,
)
from tomlkit.exceptions import TOMLKitError

from kxns_cli.exception import ConfigError
from kxns_cli.llm import ModelCapability, ProviderType
from kxns_cli.share import get_share_dir
from kxns_cli.utils.logging import logger


class OAuthRef(BaseModel):
    """Reference to OAuth credentials stored outside the config file."""

    storage: Literal["keyring", "file"] = "file"
    """Credential storage backend."""
    key: str
    """Storage key to locate OAuth credentials."""


class LLMProvider(BaseModel):
    """LLM provider configuration."""

    type: ProviderType
    """Provider type"""
    base_url: str
    """API base URL"""
    api_key: SecretStr
    """API key"""
    env: dict[str, str] | None = None
    """Environment variables to set before creating the provider instance"""
    custom_headers: dict[str, str] | None = None
    """Custom headers to include in API requests"""
    oauth: OAuthRef | None = None
    """OAuth credential reference (do not store tokens here)."""
    reasoning_key: str | None = None
    """Key name for reasoning/thinking content in API response (e.g. 'reasoning_content' for DeepSeek)"""

    @field_serializer("api_key", when_used="json")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class LLMModel(BaseModel):
    """LLM model configuration."""

    provider: str
    """Provider name"""
    model: str
    """Model name"""
    max_context_size: int
    """Maximum context size (unit: tokens)"""
    capabilities: set[ModelCapability] | None = None
    """Model capabilities"""


class LoopControl(BaseModel):
    """Agent loop control configuration."""

    max_steps_per_turn: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices("max_steps_per_turn", "max_steps_per_run"),
    )
    """Maximum number of steps in one turn"""
    max_retries_per_step: int = Field(default=3, ge=1)
    """Maximum number of retries in one step"""
    max_ralph_iterations: int = Field(default=0, ge=-1)
    """Extra iterations after the first turn in Ralph mode. Use -1 for unlimited."""
    reserved_context_size: int = Field(default=50_000, ge=1000)
    """Reserved token count for LLM response generation. Auto-compaction triggers when
    either context_tokens + reserved_context_size >= max_context_size or
    context_tokens >= max_context_size * compaction_trigger_ratio. Default is 50000."""
    compaction_trigger_ratio: float = Field(default=0.85, ge=0.5, le=0.99)
    """Context usage ratio threshold for auto-compaction. Default is 0.85 (85%).
    Auto-compaction triggers when context_tokens >= max_context_size * compaction_trigger_ratio
    or when context_tokens + reserved_context_size >= max_context_size."""


class WebSearchConfig(BaseModel):
    """Web Search service configuration."""

    base_url: str
    api_key: SecretStr
    custom_headers: dict[str, str] | None = None
    oauth: OAuthRef | None = None

    @field_serializer("api_key", when_used="json")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class WebFetchConfig(BaseModel):
    """Web Fetch service configuration."""

    base_url: str
    api_key: SecretStr
    custom_headers: dict[str, str] | None = None
    oauth: OAuthRef | None = None

    @field_serializer("api_key", when_used="json")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class Services(BaseModel):
    """Services configuration."""

    model_config = {"populate_by_name": True}

    web_search: WebSearchConfig | None = Field(default=None, alias="moonshot_search")
    web_fetch: WebFetchConfig | None = Field(default=None, alias="moonshot_fetch")


class MCPClientConfig(BaseModel):
    """MCP client configuration."""

    tool_call_timeout_ms: int = 120000
    """Timeout for tool calls in milliseconds."""
    connect_timeout_ms: int = 30000
    """Timeout when connecting to an MCP server at startup (list_tools)."""


class LLMClientConfig(BaseModel):
    """LLM HTTP client timeouts."""

    request_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="HTTP timeout for each LLM API request (seconds)",
    )
    scan_request_timeout_seconds: int = Field(
        default=240,
        ge=30,
        le=1800,
        description="Shorter LLM timeout for scan worker jobs",
    )


class MCPConfig(BaseModel):
    """MCP configuration."""

    client: MCPClientConfig = Field(
        default_factory=MCPClientConfig, description="MCP client configuration"
    )


class BlackboardConfig(BaseModel):
    """Blackboard (PostgreSQL) configuration."""

    enabled: bool = True
    # 默认 memory，避免无 PostgreSQL 时普通对话/自动扫描被硬失败
    backend: Literal["postgres", "memory"] = "memory"
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "kxns"
    password: SecretStr = SecretStr("kxns")
    database: str = "kxns_blackboard"
    pool_size: int = Field(default=5, ge=1, le=50)
    require_postgres: bool = Field(
        default=False,
        description="If true, fail when PostgreSQL is unavailable instead of memory fallback",
    )

    @field_serializer("password", when_used="json")
    def dump_bb_secret(self, v: SecretStr):
        return v.get_secret_value()


# Attack tool approval actions — auto-approved when authorized_attack is enabled
AUTHORIZED_AUTO_APPROVE_ACTIONS: frozenset[str] = frozenset(
    {
        "run command",
        "run kali tool",
        "burp attack",
        "fetch url",
        "mcp:*",
    }
)


class ScanOrchestrationConfig(BaseModel):
    """Scan orchestration defaults."""

    max_concurrency: int = Field(default=4, ge=1, le=32)
    max_depth: int = Field(default=2, ge=0, le=10)
    default_severity_filter: list[str] = Field(default_factory=lambda: ["high", "critical"])
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_max_slots: int = Field(default=8, ge=1, le=64)
    redis_enabled: bool = True
    confirmed_only_reports: bool = Field(
        default=True,
        description="Final scan reports include only confirmed findings",
    )
    strict_finding_validation: bool = Field(
        default=True,
        description="Reject invalid ReportFinding submissions (esp. confirmed without POC)",
    )
    precheck_enabled: bool = Field(
        default=True,
        description="Run environment precheck before starting scans",
    )
    authorized_attack: bool = Field(
        default=False,
        description="Global authorized pentest mode: YOLO + auto-approve attack tools",
    )
    auto_record_kali_findings: bool = Field(
        default=True,
        description="RunKali structured output auto-writes candidate findings to blackboard",
    )
    job_timeout_seconds: int = Field(
        default=1800,
        ge=60,
        le=7200,
        description="Max seconds per scan soul job before timeout",
    )
    evaluate_confidence_min: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum evaluate confidence to proceed to confirm phase",
    )
    auto_scan_on_hunt_intent: bool = Field(
        default=False,
        description="When user asks to hunt vulns with a URL, auto-start ScanManager",
    )
    prompt_enrichment_enabled: bool = Field(
        default=True,
        description="Inject optimized hunt brief into scan job prompts",
    )
    job_stall_seconds: int = Field(
        default=180,
        ge=60,
        le=3600,
        description="Cancel scan job if no wire output for this many seconds",
    )
    heartbeat_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Emit ScanRunning heartbeat interval during scan jobs",
    )
    scan_max_steps_per_turn: int = Field(
        default=40,
        ge=5,
        le=200,
        description="Max agent steps per scan worker job (lower than interactive default)",
    )


class Config(BaseModel):
    """Main configuration structure."""

    is_from_default_location: bool = Field(
        default=False,
        description="Whether the config was loaded from the default location",
        exclude=True,
    )
    source_file: Path | None = Field(
        default=None,
        description="Path to the loaded config file. None when loaded from --config text.",
        exclude=True,
    )
    default_model: str = Field(default="", description="Default model to use")
    default_thinking: bool = Field(default=False, description="Default thinking mode")
    default_yolo: bool = Field(default=False, description="Default yolo (auto-approve) mode")
    default_editor: str = Field(
        default="",
        description="Default external editor command (e.g. 'vim', 'code --wait')",
    )
    models: dict[str, LLMModel] = Field(default_factory=dict, description="List of LLM models")
    providers: dict[str, LLMProvider] = Field(
        default_factory=dict, description="List of LLM providers"
    )
    loop_control: LoopControl = Field(default_factory=LoopControl, description="Agent loop control")
    services: Services = Field(default_factory=Services, description="Services configuration")
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP configuration")
    llm_client: LLMClientConfig = Field(
        default_factory=LLMClientConfig, description="LLM HTTP client settings"
    )
    blackboard: BlackboardConfig | None = Field(
        default_factory=BlackboardConfig, description="Blackboard storage configuration"
    )
    scan: ScanOrchestrationConfig = Field(
        default_factory=ScanOrchestrationConfig, description="Scan orchestration defaults"
    )

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if self.default_model and self.default_model not in self.models:
            raise ValueError(f"Default model {self.default_model} not found in models")
        for model in self.models.values():
            if model.provider not in self.providers:
                raise ValueError(f"Provider {model.provider} not found in providers")
        return self


def get_config_file() -> Path:
    """Get the configuration file path."""
    return get_share_dir() / "config.toml"


def get_default_config() -> Config:
    """Get the default configuration."""
    return Config(
        default_model="",
        models={},
        providers={},
        services=Services(),
    )


def load_config(config_file: Path | None = None) -> Config:
    """
    Load configuration from config file.
    If the config file does not exist, create it with default configuration.

    Args:
        config_file (Path | None): Path to the configuration file. If None, use default path.

    Returns:
        Validated Config object.

    Raises:
        ConfigError: If the configuration file is invalid.
    """
    default_config_file = get_config_file().expanduser().resolve(strict=False)
    if config_file is None:
        config_file = default_config_file
    config_file = config_file.expanduser().resolve(strict=False)
    is_default_config_file = config_file == default_config_file
    logger.debug("Loading config from file: {file}", file=config_file)

    # If the user hasn't provided an explicit config path, migrate legacy JSON config once.
    if is_default_config_file and not config_file.exists():
        _migrate_json_config_to_toml()

    if not config_file.exists():
        config = get_default_config()
        logger.debug("No config file found, creating default config: {config}", config=config)
        save_config(config, config_file)
        config.is_from_default_location = is_default_config_file
        config.source_file = config_file
        return config

    try:
        config_text = config_file.read_text(encoding="utf-8")
        if config_file.suffix.lower() == ".json":
            data = json.loads(config_text)
        else:
            data = tomlkit.loads(config_text)
        config = Config.model_validate(data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in configuration file {config_file}: {e}") from e
    except TOMLKitError as e:
        raise ConfigError(f"Invalid TOML in configuration file {config_file}: {e}") from e
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration file {config_file}: {e}") from e
    config.is_from_default_location = is_default_config_file
    config.source_file = config_file
    return config


def load_config_from_string(config_string: str) -> Config:
    """
    Load configuration from a TOML or JSON string.

    Args:
        config_string (str): TOML or JSON configuration text.

    Returns:
        Validated Config object.

    Raises:
        ConfigError: If the configuration text is invalid.
    """
    if not config_string.strip():
        raise ConfigError("Configuration text cannot be empty")

    json_error: json.JSONDecodeError | None = None
    try:
        data = json.loads(config_string)
    except json.JSONDecodeError as exc:
        json_error = exc
        data = None

    if data is None:
        try:
            data = tomlkit.loads(config_string)
        except TOMLKitError as toml_error:
            raise ConfigError(
                f"Invalid configuration text: {json_error}; {toml_error}"
            ) from toml_error

    try:
        config = Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration text: {e}") from e
    config.is_from_default_location = False
    config.source_file = None
    return config


def save_config(config: Config, config_file: Path | None = None):
    """
    Save configuration to config file.

    Args:
        config (Config): Config object to save.
        config_file (Path | None): Path to the configuration file. If None, use default path.
    """
    config_file = config_file or get_config_file()
    logger.debug("Saving config to file: {file}", file=config_file)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_data = config.model_dump(mode="json", exclude_none=True)
    with open(config_file, "w", encoding="utf-8") as f:
        if config_file.suffix.lower() == ".json":
            f.write(json.dumps(config_data, ensure_ascii=False, indent=2))
        else:
            f.write(tomlkit.dumps(config_data))  # type: ignore[reportUnknownMemberType]


def _migrate_json_config_to_toml() -> None:
    old_json_config_file = get_share_dir() / "config.json"
    new_toml_config_file = get_share_dir() / "config.toml"

    if not old_json_config_file.exists():
        return
    if new_toml_config_file.exists():
        return

    logger.info(
        "Migrating legacy config file from {old} to {new}",
        old=old_json_config_file,
        new=new_toml_config_file,
    )

    try:
        with open(old_json_config_file, encoding="utf-8") as f:
            data = json.load(f)
        config = Config.model_validate(data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in legacy configuration file: {e}") from e
    except ValidationError as e:
        raise ConfigError(f"Invalid legacy configuration file: {e}") from e

    # Write new TOML config, then keep a backup of the original JSON file.
    save_config(config, new_toml_config_file)
    backup_path = old_json_config_file.with_name("config.json.bak")
    old_json_config_file.replace(backup_path)
    logger.info("Legacy config backed up to {file}", file=backup_path)
