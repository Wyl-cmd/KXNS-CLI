from __future__ import annotations

import platform
import sys
from pathlib import Path

from inline_snapshot import snapshot


def test_pyinstaller_datas():
    from kxns_cli.utils.pyinstaller import datas

    project_root = Path(__file__).parent.parent.parent
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = f".venv/lib/python{python_version}/site-packages"
    rg_binary = "rg.exe" if platform.system() == "Windows" else "rg"
    has_rg_binary = (project_root / "src/kxns_cli/deps/bin" / rg_binary).exists()
    datas = [
        (
            Path(path)
            .relative_to(project_root)
            .as_posix()
            .replace(".venv/Lib/site-packages", site_packages),
            Path(dst).as_posix(),
        )
        for path, dst in datas
    ]

    datas = [(p, d) for p, d in datas if "web/static" not in d]

    expected_datas = [
        (
            f"{site_packages}/dateparser/data/dateparser_tz_cache.pkl",
            "dateparser/data",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/INSTALLER",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/METADATA",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/RECORD",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/REQUESTED",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/WHEEL",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/entry_points.txt",
            "fastmcp/../fastmcp-2.12.5.dist-info",
        ),
        (
            f"{site_packages}/fastmcp/../fastmcp-2.12.5.dist-info/licenses/LICENSE",
            "fastmcp/../fastmcp-2.12.5.dist-info/licenses",
        ),
        (
            "src/kxns_cli/CHANGELOG.md",
            "kxns_cli",
        ),
        ("src/kxns_cli/agents/default/agent.yaml", "kxns_cli/agents/default"),
        ("src/kxns_cli/agents/default/sub.yaml", "kxns_cli/agents/default"),
        ("src/kxns_cli/agents/default/system.md", "kxns_cli/agents/default"),
        ("src/kxns_cli/agents/okabe/agent.yaml", "kxns_cli/agents/okabe"),
        ("src/kxns_cli/prompts/compact.md", "kxns_cli/prompts"),
        ("src/kxns_cli/prompts/init.md", "kxns_cli/prompts"),
        (
            "src/kxns_cli/skills/kxns-cli-help/SKILL.md",
            "kxns_cli/skills/kxns-cli-help",
        ),
        (
            "src/kxns_cli/skills/skill-creator/SKILL.md",
            "kxns_cli/skills/skill-creator",
        ),
        ("src/kxns_cli/tools/ask_user/description.md", "kxns_cli/tools/ask_user"),
        (
            "src/kxns_cli/tools/dmail/dmail.md",
            "kxns_cli/tools/dmail",
        ),
        (
            "src/kxns_cli/tools/file/glob.md",
            "kxns_cli/tools/file",
        ),
        (
            "src/kxns_cli/tools/file/grep.md",
            "kxns_cli/tools/file",
        ),
        (
            "src/kxns_cli/tools/file/read.md",
            "kxns_cli/tools/file",
        ),
        (
            "src/kxns_cli/tools/file/read_media.md",
            "kxns_cli/tools/file",
        ),
        (
            "src/kxns_cli/tools/file/replace.md",
            "kxns_cli/tools/file",
        ),
        (
            "src/kxns_cli/tools/file/write.md",
            "kxns_cli/tools/file",
        ),
        ("src/kxns_cli/tools/multiagent/create.md", "kxns_cli/tools/multiagent"),
        ("src/kxns_cli/tools/multiagent/task.md", "kxns_cli/tools/multiagent"),
        ("src/kxns_cli/tools/shell/bash.md", "kxns_cli/tools/shell"),
        ("src/kxns_cli/tools/shell/powershell.md", "kxns_cli/tools/shell"),
        (
            "src/kxns_cli/tools/think/think.md",
            "kxns_cli/tools/think",
        ),
        (
            "src/kxns_cli/tools/todo/set_todo_list.md",
            "kxns_cli/tools/todo",
        ),
        (
            "src/kxns_cli/tools/web/fetch.md",
            "kxns_cli/tools/web",
        ),
        (
            "src/kxns_cli/tools/web/search.md",
            "kxns_cli/tools/web",
        ),
    ]
    if has_rg_binary:
        expected_datas.append((f"src/kxns_cli/deps/bin/{rg_binary}", "kxns_cli/deps/bin"))

    assert sorted(datas) == snapshot([
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/INSTALLER",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/METADATA",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/RECORD",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/REQUESTED",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/WHEEL",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/entry_points.txt",
        "fastmcp/../fastmcp-2.12.5.dist-info",
    ),
    (
        ".venv/lib/python3.14/site-packages/fastmcp/../fastmcp-2.12.5.dist-info/licenses/LICENSE",
        "fastmcp/../fastmcp-2.12.5.dist-info/licenses",
    ),
    ("src/kxns_cli/CHANGELOG.md", "kxns_cli"),
    ("src/kxns_cli/agents/default/agent.yaml", "kxns_cli/agents/default"),
    ("src/kxns_cli/agents/default/sub.yaml", "kxns_cli/agents/default"),
    ("src/kxns_cli/agents/default/system.md", "kxns_cli/agents/default"),
    ("src/kxns_cli/agents/okabe/agent.yaml", "kxns_cli/agents/okabe"),
    ("src/kxns_cli/prompts/compact.md", "kxns_cli/prompts"),
    ("src/kxns_cli/prompts/init.md", "kxns_cli/prompts"),
    ("src/kxns_cli/skills/kxns-cli-help/SKILL.md", "kxns_cli/skills/kxns-cli-help"),
    ("src/kxns_cli/skills/skill-creator/SKILL.md", "kxns_cli/skills/skill-creator"),
    ("src/kxns_cli/tools/ask_user/description.md", "kxns_cli/tools/ask_user"),
    ("src/kxns_cli/tools/dmail/dmail.md", "kxns_cli/tools/dmail"),
    ("src/kxns_cli/tools/file/glob.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/file/grep.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/file/read.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/file/read_media.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/file/replace.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/file/write.md", "kxns_cli/tools/file"),
    ("src/kxns_cli/tools/multiagent/create.md", "kxns_cli/tools/multiagent"),
    ("src/kxns_cli/tools/multiagent/task.md", "kxns_cli/tools/multiagent"), ("src/kxns_cli/tools/plan/description.md", "kxns_cli/tools/plan"), ("src/kxns_cli/tools/plan/enter_description.md", "kxns_cli/tools/plan"), ("src/kxns_cli/tools/plan/enter_description_yolo.md", "kxns_cli/tools/plan"), ("src/kxns_cli/tools/shell/bash.md", "kxns_cli/tools/shell"),
    ("src/kxns_cli/tools/shell/powershell.md", "kxns_cli/tools/shell"),
    ("src/kxns_cli/tools/think/think.md", "kxns_cli/tools/think"),
    ("src/kxns_cli/tools/todo/set_todo_list.md", "kxns_cli/tools/todo"),
    ("src/kxns_cli/tools/web/fetch.md", "kxns_cli/tools/web"),
    ("src/kxns_cli/tools/web/search.md", "kxns_cli/tools/web"),
])


def test_pyinstaller_hiddenimports():
    from kxns_cli.utils.pyinstaller import hiddenimports

    assert sorted(hiddenimports) == snapshot(
        ["kaos", "kaos._current", "kaos.local", "kaos.path", "kaos.ssh", "kosong", "kosong.__main__", "kosong._generate", "kosong.chat_provider", "kosong.chat_provider.chaos", "kosong.chat_provider.echo", "kosong.chat_provider.echo.dsl", "kosong.chat_provider.echo.echo", "kosong.chat_provider.echo.scripted_echo", "kosong.chat_provider.kimi", "kosong.chat_provider.mock", "kosong.chat_provider.openai_common", "kosong.contrib", "kosong.contrib.chat_provider", "kosong.contrib.chat_provider.anthropic", "kosong.contrib.chat_provider.common", "kosong.contrib.chat_provider.google_genai", "kosong.contrib.chat_provider.openai_legacy", "kosong.contrib.chat_provider.openai_responses", "kosong.contrib.context", "kosong.contrib.context.linear", "kosong.message", "kosong.tooling", "kosong.tooling.empty", "kosong.tooling.error", "kosong.tooling.mcp", "kosong.tooling.simple", "kosong.utils", "kosong.utils.aio", "kosong.utils.jsonschema", "kosong.utils.typing", "kxns_cli", "kxns_cli.agentspec", "kxns_cli.app", "kxns_cli.auth", "kxns_cli.auth.oauth", "kxns_cli.auth.platforms", "kxns_cli.cli", "kxns_cli.cli.__main__", "kxns_cli.cli.info", "kxns_cli.cli.mcp", "kxns_cli.cli.toad", "kxns_cli.cli.web", "kxns_cli.config", "kxns_cli.constant", "kxns_cli.exception", "kxns_cli.llm", "kxns_cli.metadata", "kxns_cli.prompts", "kxns_cli.session", "kxns_cli.session_state", "kxns_cli.share", "kxns_cli.skill", "kxns_cli.skill.flow", "kxns_cli.skill.flow.d2", "kxns_cli.skill.flow.mermaid", "kxns_cli.soul", "kxns_cli.soul.agent", "kxns_cli.soul.approval", "kxns_cli.soul.compaction", "kxns_cli.soul.context", "kxns_cli.soul.denwarenji", "kxns_cli.soul.kxnssoul", "kxns_cli.soul.message", "kxns_cli.soul.slash", "kxns_cli.soul.toolset", "kxns_cli.tools",
            "kxns_cli.tools.ask_user",
            "kxns_cli.tools.display",
            "kxns_cli.tools.dmail",
            "kxns_cli.tools.file",
            "kxns_cli.tools.file.glob",
            "kxns_cli.tools.file.grep_local",
            "kxns_cli.tools.file.read",
            "kxns_cli.tools.file.read_media",
            "kxns_cli.tools.file.replace",
            "kxns_cli.tools.file.utils",
            "kxns_cli.tools.file.write",
            "kxns_cli.tools.multiagent",
            "kxns_cli.tools.multiagent.create",
            "kxns_cli.tools.multiagent.task", "kxns_cli.tools.plan", "kxns_cli.tools.plan.enter", "kxns_cli.tools.shell",
            "kxns_cli.tools.test",
            "kxns_cli.tools.think",
            "kxns_cli.tools.todo",
            "kxns_cli.tools.utils",
            "kxns_cli.tools.web",
            "kxns_cli.tools.web.fetch",
            "kxns_cli.tools.web.search", "kxns_cli.ui", "kxns_cli.ui.print", "kxns_cli.ui.print.visualize", "kxns_cli.ui.shell", "kxns_cli.ui.shell.console", "kxns_cli.ui.shell.debug", "kxns_cli.ui.shell.export_import", "kxns_cli.ui.shell.keyboard", "kxns_cli.ui.shell.oauth", "kxns_cli.ui.shell.prompt", "kxns_cli.ui.shell.replay", "kxns_cli.ui.shell.setup", "kxns_cli.ui.shell.slash", "kxns_cli.ui.shell.update", "kxns_cli.ui.shell.usage", "kxns_cli.ui.shell.visualize", "kxns_cli.utils", "kxns_cli.utils.aiohttp", "kxns_cli.utils.aioqueue", "kxns_cli.utils.broadcast", "kxns_cli.utils.changelog", "kxns_cli.utils.clipboard", "kxns_cli.utils.datetime", "kxns_cli.utils.diff", "kxns_cli.utils.editor", "kxns_cli.utils.environment", "kxns_cli.utils.envvar", "kxns_cli.utils.export", "kxns_cli.utils.frontmatter", "kxns_cli.utils.io", "kxns_cli.utils.logging", "kxns_cli.utils.media_tags", "kxns_cli.utils.message", "kxns_cli.utils.path", "kxns_cli.utils.proctitle", "kxns_cli.utils.pyinstaller", "kxns_cli.utils.rich", "kxns_cli.utils.rich.columns", "kxns_cli.utils.rich.markdown", "kxns_cli.utils.rich.syntax", "kxns_cli.utils.signals", "kxns_cli.utils.slashcmd", "kxns_cli.utils.string", "kxns_cli.utils.subprocess_env", "kxns_cli.utils.term", "kxns_cli.utils.typing", "kxns_cli.web", "kxns_cli.web.api", "kxns_cli.web.api.config", "kxns_cli.web.api.open_in", "kxns_cli.web.api.sessions", "kxns_cli.web.app", "kxns_cli.web.auth", "kxns_cli.web.models", "kxns_cli.web.runner", "kxns_cli.web.runner.messages", "kxns_cli.web.runner.process", "kxns_cli.web.runner.worker", "kxns_cli.web.store", "kxns_cli.web.store.sessions", "kxns_cli.wire", "kxns_cli.wire.file", "kxns_cli.wire.jsonrpc", "kxns_cli.wire.protocol", "kxns_cli.wire.serde", "kxns_cli.wire.server", "kxns_cli.wire.types", "setproctitle",
        ]
    )
