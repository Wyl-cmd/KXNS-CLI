"""Open local apps for a path on the host machine."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/open-in", tags=["open-in"])

# OPEN-11: LAN 模式下拒绝访问的敏感家目录子路径（与 sessions.py 的 SENSITIVE_HOME_PATHS 对齐）
_SENSITIVE_HOME_PATHS = frozenset({".ssh", ".aws", ".gnupg", ".config", ".kube"})


class OpenInRequest(BaseModel):
    """Open path in a local app."""

    app: Literal["finder", "explorer", "cursor", "vscode", "iterm", "terminal", "antigravity"]
    path: str


class OpenInResponse(BaseModel):
    """Open path response."""

    ok: bool
    detail: str | None = None


def _escape_applescript_string(s: str) -> str:
    """转义 AppleScript 字符串中的特殊字符（OPEN-10）。

    AppleScript 字符串用双引号包裹，其中的 `\\` 和 `"` 需转义，
    防止路径名含这些字符时破坏脚本结构、执行任意 AppleScript。
    """
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _is_sensitive_path(path: Path) -> bool:
    """检查路径是否指向敏感家目录子路径（OPEN-11）。

    与 sessions.py 的 `_is_path_in_sensitive_location` 逻辑对齐，
    用于 LAN 模式下拒绝访问 `~/.ssh`、`~/.aws` 等敏感目录。
    """
    try:
        home = Path.home()
        if path.is_relative_to(home):
            rel_to_home = path.relative_to(home)
            first_part = rel_to_home.parts[0] if rel_to_home.parts else ""
            if first_part in _SENSITIVE_HOME_PATHS:
                return True
    except (ValueError, RuntimeError):
        pass
    return False


def _resolve_path(path: str) -> Path:
    """Resolve and validate a path (file or directory)."""
    resolved = Path(path).expanduser()
    try:
        resolved = resolved.resolve()
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path does not exist: {path}",
        ) from None

    if not resolved.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path does not exist: {path}",
        )
    return resolved


def _run_command(args: list[str]) -> None:
    subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )


def _open_app(app_name: str, path: Path, fallback: str | None = None) -> None:
    try:
        _run_command(["open", "-a", app_name, str(path)])
        return
    except subprocess.CalledProcessError as exc:
        if fallback is None:
            raise
        logger.warning("Open with {} failed: {}", app_name, exc)
    _run_command(["open", "-a", fallback, str(path)])


def _open_terminal(path: Path) -> None:
    # OPEN-10: 转义 path 中的 AppleScript 特殊字符，防止命令注入
    safe_path = _escape_applescript_string(str(path))
    script = f'tell application "Terminal" to do script "cd " & quoted form of "{safe_path}"'
    _run_command(["osascript", "-e", script])


def _open_iterm(path: Path) -> None:
    # OPEN-10: 转义 path 中的 AppleScript 特殊字符，防止命令注入
    safe_path = _escape_applescript_string(str(path))
    script = "\n".join(
        [
            'tell application "iTerm"',
            "  create window with default profile",
            "  tell current session of current window",
            f'    write text "cd " & quoted form of "{safe_path}"',
            "  end tell",
            "end tell",
        ]
    )
    try:
        _run_command(["osascript", "-e", script])
    except subprocess.CalledProcessError:
        script = script.replace('"iTerm"', '"iTerm2"')
        _run_command(["osascript", "-e", script])


@router.post("", summary="Open a path in a local application")
async def open_in(request: OpenInRequest, http_request: Request) -> OpenInResponse:
    path = _resolve_path(request.path)

    # OPEN-11: LAN 模式下拒绝访问敏感路径（~/.ssh、~/.aws 等）
    # restrict_sensitive_apis=True 时此 router 不挂载（app.py:225-226），无需校验
    lan_only = getattr(http_request.app.state, "lan_only", False)
    if lan_only and _is_sensitive_path(path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to sensitive paths is not allowed in LAN-only mode.",
        )

    is_file = path.is_file()

    try:
        if sys.platform == "win32":
            match request.app:
                case "finder" | "explorer":
                    if is_file:
                        _run_command(["explorer", "/select,", str(path)])
                    else:
                        os.startfile(str(path))
                case "cursor":
                    _run_command(["cursor", str(path)])
                case "vscode":
                    _run_command(["code", str(path)])
                case "terminal":
                    directory = path.parent if is_file else path
                    # OPEN-10: 用引号包裹 directory，防止 & 等字符执行额外 cmd
                    _run_command(["cmd", "/c", "start", "cmd", "/k", f'cd /d "{directory}"'])
                case _:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported app on Windows: {request.app}",
                    )
        elif sys.platform == "darwin":
            match request.app:
                case "finder":
                    if is_file:
                        _run_command(["open", "-R", str(path)])
                    else:
                        _run_command(["open", str(path)])
                case "cursor":
                    _open_app("Cursor", path)
                case "vscode":
                    _open_app("Visual Studio Code", path, fallback="Code")
                case "antigravity":
                    _open_app("Antigravity", path)
                case "iterm":
                    directory = path.parent if is_file else path
                    _open_iterm(directory)
                case "terminal":
                    directory = path.parent if is_file else path
                    _open_terminal(directory)
                case _:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported app: {request.app}",
                    )
        else:
            match request.app:
                case "finder" | "explorer":
                    _run_command(["xdg-open", str(path)])
                case "cursor":
                    _run_command(["cursor", str(path)])
                case "vscode":
                    _run_command(["code", str(path)])
                case "terminal":
                    directory = path.parent if is_file else path
                    # OPEN-10: 用 shlex.quote 转义 directory，防止 ; 等字符执行额外 shell
                    _run_command(["xdg-terminal-emulator", f"cd {shlex.quote(str(directory))}"])
                case _:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported app on Linux: {request.app}",
                    )
    except subprocess.CalledProcessError as exc:
        logger.warning("Open-in failed ({}): {}", request.app, exc)
        detail = exc.stderr.strip() if exc.stderr else "Failed to open application."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc

    return OpenInResponse(ok=True)
