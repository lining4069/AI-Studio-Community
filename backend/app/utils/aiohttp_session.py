"""
aiohttp session singleton management for shared use across the application.
"""

import aiohttp


class HttpSessionShared:
    _session: aiohttp.ClientSession | None = None

    @classmethod
    async def ensure_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return cls._session

    @classmethod
    async def cleanup(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None
