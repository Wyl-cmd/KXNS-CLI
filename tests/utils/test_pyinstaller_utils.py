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
        [
            "kxns_cli.tools",
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
            "kxns_cli.tools.web.search",
            "setproctitle",
        ]
    )
