from __future__ import annotations

import ssl

import aiohttp
import certifi

_ssl_context = ssl.create_default_context(cafile=certifi.where())


def new_client_session(*, timeout_seconds: float = 60.0) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=_ssl_context),
        timeout=timeout,
    )
