"""API routes."""

from kxns_cli.web.api import config, open_in, sessions

config_router = config.router
sessions_router = sessions.router
open_in_router = open_in.router
work_dirs_router = sessions.work_dirs_router

__all__ = ["config_router", "sessions_router", "open_in_router", "work_dirs_router"]
