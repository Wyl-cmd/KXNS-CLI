from __future__ import annotations

# ruff: noqa

import platform

import pytest
from kosong.tooling import Tool

from kxns_cli.agentspec import DEFAULT_AGENT_FILE
from kxns_cli.soul.agent import Runtime, load_agent


@pytest.mark.skipif(platform.system() == "Windows", reason="Skipping test on Windows")
async def test_default_agent(runtime: Runtime):
    agent = await load_agent(DEFAULT_AGENT_FILE, runtime, mcp_configs=[])

    assert "Kxns Hunter" in agent.system_prompt or "KXNS" in agent.system_prompt
    assert str(runtime.builtin_args.KXNS_WORK_DIR) in agent.system_prompt

    tool_names = {t.name for t in agent.toolset.tools if isinstance(t, Tool)}
    assert {
        "Shell",
        "ReadFile",
        "WriteFile",
        "StrReplaceFile",
        "Glob",
        "Grep",
        "SearchWeb",
        "FetchURL",
    }.issubset(tool_names)
