"""Worker module for running KxnsCLI in a subprocess.

This module is the entry point for the subprocess that runs KxnsCLI in wire mode.
It reads the session configuration from disk and runs KxnsCLI.run_wire_stdio().

Usage:
    python -m kxns_cli.web.runner.worker <session_id>
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from uuid import UUID

from loguru import logger

from kxns_cli.app import KxnsCLI, enable_logging
from kxns_cli.cli.mcp import get_global_mcp_config_file
from kxns_cli.exception import MCPConfigError
from kxns_cli.web.store.sessions import load_session_by_id


async def run_worker(session_id: UUID) -> None:
    """Run the KxnsCLI worker for a session."""
    # Find session by ID using the web store
    joint_session = load_session_by_id(session_id)
    if joint_session is None:
        raise ValueError(f"Session not found: {session_id}")

    # Get the kxns-cli session object
    session = joint_session.kxns_cli_session

    # Load default MCP config file if it exists
    default_mcp_file = get_global_mcp_config_file()
    mcp_configs: list[dict[str, Any]] = []
    if default_mcp_file.exists():
        raw = default_mcp_file.read_text(encoding="utf-8")
        try:
            mcp_configs = [json.loads(raw)]
        except json.JSONDecodeError:
            logger.warning(
                "Invalid JSON in MCP config file: {path}",
                path=default_mcp_file,
            )

    # Create KxnsCLI instance with MCP configuration
    try:
        kxns_cli = await KxnsCLI.create(session, mcp_configs=mcp_configs or None)
    except MCPConfigError as exc:
        logger.warning(
            "Invalid MCP config in {path}: {error}. Starting without MCP.",
            path=default_mcp_file,
            error=exc,
        )
        kxns_cli = await KxnsCLI.create(session, mcp_configs=None)

    # Run in wire stdio mode
    await kxns_cli.run_wire_stdio()


def main() -> None:
    """Entry point for the worker subprocess."""
    from kxns_cli.utils.proctitle import set_process_title

    set_process_title("kxns-hunter-worker")

    if len(sys.argv) < 2:
        print("Usage: python -m kxns_cli.web.runner.worker <session_id>", file=sys.stderr)
        sys.exit(1)

    try:
        session_id = UUID(sys.argv[1])
    except ValueError:
        print(f"Invalid session ID: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    # Enable logging for the subprocess
    enable_logging(debug=False, redirect_stderr=False)

    # Run the async worker
    asyncio.run(run_worker(session_id))


if __name__ == "__main__":
    main()
