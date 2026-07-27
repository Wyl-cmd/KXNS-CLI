"""回归：kxns api 写入配置必须支持带点号/斜杠的模型名，并走 KXNS_SHARE_DIR。"""

from __future__ import annotations

from pathlib import Path

import pytest

from kxns_cli.cli import _save_api_config
from kxns_cli.config import load_config
from kxns_cli.llm import create_llm
from kxns_cli.auth.oauth import OAuthManager


@pytest.mark.parametrize(
    "model_name",
    [
        "claude-3.5-sonnet",
        "openai/gpt-4o",
        "qwen2.5-72b",
    ],
)
def test_save_api_config_quoted_model_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model_name: str):
    share = tmp_path / "share"
    monkeypatch.setenv("KXNS_SHARE_DIR", str(share))

    _save_api_config(
        url="https://api.example.com/v1",
        api_key="sk-test",
        model=model_name,
        max_context_size=128000,
    )

    config_file = share / "config.toml"
    assert config_file.exists()
    raw = config_file.read_text(encoding="utf-8")
    # 点号模型名不能写成裸 TOML 表路径（会被解析成嵌套）
    assert f"[models.{model_name}]" not in raw or model_name.replace(".", "") == model_name

    config = load_config()
    assert config.default_model == model_name
    assert model_name in config.models
    assert config.models[model_name].provider == "custom"
    assert "custom" in config.providers
    assert config.providers["custom"].base_url == "https://api.example.com/v1"

    llm = create_llm(
        config.providers["custom"],
        config.models[model_name],
        thinking=False,
        session_id="test",
        oauth=OAuthManager(config),
    )
    assert llm is not None


def test_save_api_config_uses_share_dir_not_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    share = tmp_path / "custom-share"
    monkeypatch.setenv("KXNS_SHARE_DIR", str(share))
    home_kxns = Path.home() / ".kxns" / "config.toml"
    before = home_kxns.read_text(encoding="utf-8") if home_kxns.exists() else None

    _save_api_config("https://api.example.com/v1", "sk-x", "gpt-4o")

    assert (share / "config.toml").exists()
    after = home_kxns.read_text(encoding="utf-8") if home_kxns.exists() else None
    assert before == after
