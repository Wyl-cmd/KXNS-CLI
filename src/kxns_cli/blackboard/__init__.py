from __future__ import annotations

from kxns_cli.blackboard.memory import MemoryBlackboardStore
from kxns_cli.blackboard.postgres import PostgresBlackboardStore
from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.config import Config
from kxns_cli.utils.logging import logger

__all__ = [
    "BlackboardStore",
    "MemoryBlackboardStore",
    "PostgresBlackboardStore",
    "create_blackboard_store",
]


async def create_blackboard_store(config: Config, *, strict: bool | None = None) -> BlackboardStore:
    """Create blackboard store from config.

    When backend=postgres and require_postgres=True (default), connection failure
    raises instead of silently falling back to memory.
    """
    bb_config = config.blackboard
    if bb_config is None or not bb_config.enabled:
        logger.info("Blackboard: using in-memory store")
        store: BlackboardStore = MemoryBlackboardStore()
        await store.connect()
        return store

    if bb_config.backend == "memory":
        store = MemoryBlackboardStore()
        await store.connect()
        return store

    must_use_pg = strict if strict is not None else bb_config.require_postgres
    pg_store = PostgresBlackboardStore(bb_config)
    try:
        await pg_store.connect()
        logger.info(
            "Blackboard: connected to PostgreSQL at {host}:{port}",
            host=bb_config.host,
            port=bb_config.port,
        )
        return pg_store
    except Exception as exc:
        if must_use_pg:
            raise RuntimeError(
                f"PostgreSQL Blackboard required but unavailable: {exc}. "
                "Run: kxns doctor --fix  or set [blackboard] require_postgres = false"
            ) from exc
        logger.warning("Blackboard: PostgreSQL unavailable ({error}), using memory", error=exc)
        fallback = MemoryBlackboardStore()
        await fallback.connect()
        return fallback
