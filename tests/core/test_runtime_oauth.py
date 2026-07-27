"""回归：Runtime / create_llm 不得接收 oauth=None。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kaos.path import KaosPath
from pydantic import SecretStr

from kxns_cli.app import KxnsCLI
from kxns_cli.auth.oauth import OAuthManager
from kxns_cli.config import Config, LLMModel, LLMProvider
from kxns_cli.session import Session


@pytest.mark.asyncio
async def test_kxns_cli_create_passes_oauth_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    share = tmp_path / "share"
    monkeypatch.setenv("KXNS_SHARE_DIR", str(share))

    config = Config(
        default_model="gpt-4o",
        models={
            "gpt-4o": LLMModel(provider="custom", model="gpt-4o", max_context_size=128000),
        },
        providers={
            "custom": LLMProvider(
                type="openai_legacy",
                base_url="https://api.example.com/v1",
                api_key=SecretStr("sk-test"),
            ),
        },
    )
    # 黑板用 memory，避免测试依赖 Postgres
    assert config.blackboard is not None
    config.blackboard.backend = "memory"
    config.blackboard.require_postgres = False
    config.scan.authorized_attack = False

    work_dir = KaosPath.unsafe_from_local_path(tmp_path / "work")
    (tmp_path / "work").mkdir()
    session = await Session.create(work_dir)

    captured: dict[str, object] = {}

    async def fake_runtime_create(cfg, oauth, llm, sess, yolo, skills_dir=None):
        captured["oauth"] = oauth
        captured["llm"] = llm
        runtime = MagicMock()
        runtime.config = cfg
        runtime.session = sess
        runtime.llm = llm
        runtime.oauth = oauth
        runtime.approval = MagicMock()
        runtime.approval.is_yolo = MagicMock(return_value=False)
        return runtime

    fake_agent = MagicMock()
    fake_agent.runtime = MagicMock()

    with (
        patch("kxns_cli.app.create_llm") as mock_create_llm,
        patch("kxns_cli.app.Runtime.create", new=AsyncMock(side_effect=fake_runtime_create)),
        patch("kxns_cli.app.load_agent", new=AsyncMock(return_value=fake_agent)),
        patch("kxns_cli.app.Context") as mock_ctx,
    ):
        mock_create_llm.return_value = MagicMock()
        mock_ctx.return_value.restore = AsyncMock()
        await KxnsCLI.create(session=session, config=config)

    assert mock_create_llm.call_args is not None
    assert mock_create_llm.call_args.kwargs.get("oauth") is not None
    assert isinstance(mock_create_llm.call_args.kwargs["oauth"], OAuthManager)
    assert captured["oauth"] is not None
    assert isinstance(captured["oauth"], OAuthManager)
