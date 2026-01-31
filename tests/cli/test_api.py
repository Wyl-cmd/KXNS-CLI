from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from kimi_cli.cli.api import config_add, config_list, config_remove, config_set_default, config_test
from kimi_cli.config import Config, LLMModel, LLMProvider, load_config, save_config, get_config_file


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[default_model = ""]

[providers]
[models]
""")
        f.flush()
        return Path(f.name)


@pytest.fixture
def sample_config():
    """Create a sample configuration."""
    return Config(
        default_model="",
        providers={
            "openai": LLMProvider(
                type="openai_legacy",
                base_url="https://api.openai.com/v1",
                api_key="sk-test-key-123",
            ),
            "anthropic": LLMProvider(
                type="anthropic",
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test-key-456",
            ),
        },
        models={
            "gpt-4o": LLMModel(
                provider="openai",
                model="gpt-4o",
                max_context_size=128000,
                capabilities=set(),
            ),
            "claude-3-5-sonnet": LLMModel(
                provider="anthropic",
                model="claude-3-5-sonnet",
                max_context_size=200000,
                capabilities=set(),
            ),
        },
    )


def test_config_add_provider_and_model():
    """Test adding a provider and model together."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[default_model = ""]

[providers]
[models]
""")
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_add,
            [
                "--config-file",
                str(config_file),
                "-p",
                "openai",
                "-m",
                "gpt-4o",
                "-u",
                "https://api.openai.com/v1",
                "-k",
                "sk-test-key-123",
                "-C",
                "128000",
                "-c",
                "thinking,image_in",
                "-d",
            ],
        )
        
        assert result.exit_code == 0
        assert "Added API configuration: openai/gpt-4o" in result.stdout
        
        config = load_config(config_file)
        assert "openai" in config.providers
        assert config.providers["openai"].api_key.get_secret_value() == "sk-test-key-123"
        assert "gpt-4o" in config.models
        assert config.models["gpt-4o"].max_context_size == 128000
        assert config.models["gpt-4o"].capabilities == {"thinking", "image_in"}


def test_config_add_model_only():
    """Test adding a model to existing provider."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[default_model = ""]

[providers]
openai.type = "openai_legacy"
openai.base_url = "https://api.openai.com/v1"
openai.api_key = "sk-test-key-123"

[models]
gpt-4o.provider = "openai"
gpt-4o.model = "gpt-4o"
gpt-4o.max_context_size = 128000
""")
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_add,
            [
                "--config-file",
                str(config_file),
                "-p",
                "openai",
                "-m",
                "gpt-4o-mini",
                "-d",
            ],
        )
        
        assert result.exit_code == 0
        assert "Added API configuration: openai/gpt-4o-mini" in result.stdout
        
        config = load_config(config_file)
        assert "gpt-4o-mini" in config.models


def test_config_list():
    """Test listing configurations."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_list,
            ["--config-file", str(config_file)],
        )
        
        assert result.exit_code == 0
        assert "openai:" in result.stdout
        assert "anthropic:" in result.stdout
        assert "gpt-4o (default)" in result.stdout


def test_config_remove_model():
    """Test removing a model."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_remove,
            [
                "--config-file",
                str(config_file),
                "-p",
                "openai",
                "-m",
                "gpt-4o",
            ],
        )
        
        assert result.exit_code == 0
        assert "Removed API configuration: openai/gpt-4o" in result.stdout
        
        config = load_config(config_file)
        assert "gpt-4o" not in config.models


def test_config_remove_provider():
    """Test removing a provider."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_remove,
            [
                "--config-file",
                str(config_file),
                "-p",
                "anthropic",
            ],
        )
        
        assert result.exit_code == 0
        assert "Removed provider: anthropic" in result.stdout
        
        config = load_config(config_file)
        assert "anthropic" not in config.providers
        assert "claude-3-5-sonnet" not in config.models


def test_config_remove_all():
    """Test removing all configurations."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_remove,
            [
                "--config-file",
                str(config_file),
                "--all",
            ],
        )
        
        assert result.exit_code == 0
        assert "Removed all API configurations." in result.stdout
        
        config = load_config(config_file)
        assert config.providers == {}
        assert config.models == {}
        assert config.default_model == ""


def test_config_set_default():
    """Test setting default model."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_set_default,
            [
                "--config-file",
                str(config_file),
                "gpt-4o",
            ],
        )
        
        assert result.exit_code == 0
        assert "Default model set to: gpt-4o" in result.stdout
        
        config = load_config(config_file)
        assert config.default_model == "gpt-4o"


def test_config_test():
    """Test API connection."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config().model_dump(exclude_none=True))
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_test,
            [
                "--config-file",
                str(config_file),
            ],
        )
        
        assert result.exit_code == 0
        assert "Testing API connection to: openai/gpt-4o" in result.stdout
        assert "  ✓ API key is valid" in result.stdout
        assert "  ✓ Model: gpt-4o" in result.stdout
        assert "  ✓ Capabilities: [thinking, image_in]" in result.stdout


def test_config_add_with_headers():
    """Test adding configuration with custom headers."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[default_model = ""]

[providers]
[models]
""")
        f.flush()
        config_file = Path(f.name)
        
        runner = CliRunner()
        result = runner.invoke(
            config_add,
            [
                "--config-file",
                str(config_file),
                "-p",
                "openai",
                "-m",
                "gpt-4o",
                "-H",
                "X-Custom-Header: custom-value",
                "-H",
                "Authorization: Bearer token123",
            ],
        )
        
        assert result.exit_code == 0
        
        config = load_config(config_file)
        assert config.providers["openai"].custom_headers == {
            "X-Custom-Header": "custom-value",
            "Authorization": "Bearer token123",
        }


def test_config_error_missing_provider():
    """Test error when provider is not specified."""
    runner = CliRunner()
    result = runner.invoke(
        config_add,
            [
                "-m",
                "gpt-4o",
                "-u",
                "https://api.openai.com/v1",
                "-k",
                "sk-test-key-123",
            ],
        )
        
    assert result.exit_code == 2
    assert "--provider is required" in result.stdout


def test_config_error_invalid_capability():
    """Test error when invalid capability is specified."""
    runner = CliRunner()
    result = runner.invoke(
        config_add,
            [
                "-p",
                "openai",
                "-m",
                "gpt-4o",
                "-c",
                "invalid_cap",
            ],
        )
        
    assert result.exit_code == 1
    assert "Invalid capability: invalid_cap" in result.stdout
