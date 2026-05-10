from __future__ import annotations


class KxnsCLIException(Exception):
    """Base exception class for Kxns CLI."""

    pass


class ConfigError(KxnsCLIException, ValueError):
    """Configuration error."""

    pass


class AgentSpecError(KxnsCLIException, ValueError):
    """Agent specification error."""

    pass


class InvalidToolError(KxnsCLIException, ValueError):
    """Invalid tool error."""

    pass


class SystemPromptTemplateError(KxnsCLIException, ValueError):
    """System prompt template error."""

    pass


class MCPConfigError(KxnsCLIException, ValueError):
    """MCP config error."""

    pass


class MCPRuntimeError(KxnsCLIException, RuntimeError):
    """MCP runtime error."""

    pass
