"""Cache backend abstraction, with a stdlib-SQLite implementation.

Caches sit at the provider-response layer (e.g. sold comps, search hits) so
prompt/report changes never require a cache flush.
"""

import asyncio
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fastapi import Depends

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class CacheBackend(ABC):
    """Interface for a key/value cache with per-entry TTL expiry."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return the cached value for `key`, or `None` if missing/expired."""
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        """Store `value` under `key`, expiring after `ttl_seconds`."""
        raise NotImplementedError


class SqliteCacheBackend(CacheBackend):
    """Cache backend backed by a stdlib `sqlite3` file, with lazy expiry.

    Every operation opens and closes its own connection inside
    `asyncio.to_thread`, since sqlite3 connections are not safe to share
    across the threads used by the default asyncio executor.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL)"
            )
            conn.commit()
        finally:
            conn.close()

    async def get(self, key: str) -> Any | None:
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> Any | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at < time.time():
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None
            return json.loads(value)
        finally:
            conn.close()

    async def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        await asyncio.to_thread(self._set_sync, key, value, ttl_seconds)

    def _set_sync(self, key: str, value: Any, ttl_seconds: int) -> None:
        conn = self._connect()
        try:
            expires_at = time.time() + ttl_seconds
            conn.execute(
                "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "expires_at = excluded.expires_at",
                (key, json.dumps(value), expires_at),
            )
            conn.commit()
        finally:
            conn.close()


class NullCacheBackend(CacheBackend):
    """No-op cache backend used when caching is disabled (e.g. in tests)."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        return None


def build_cache_key(*parts: str, kind: str, schema_version: int) -> str:
    """Build a stable cache key from normalized parts, a kind, and a schema version.

    Normalization lowercases and collapses whitespace so equivalent queries
    (e.g. differing only in case) share a cache entry. Bumping
    `schema_version` invalidates all previously cached entries for `kind`.
    """
    normalized_parts = " ".join(" ".join(part.strip().lower().split()) for part in parts)
    return f"{kind}:v{schema_version}:{normalized_parts}"


def get_cache_backend(settings: Settings = Depends(get_settings)) -> CacheBackend:
    """Factory selecting a cache backend implementation from settings.

    `settings` defaults to a FastAPI sub-dependency (`Depends(get_settings)`) so this
    also works as a route dependency without FastAPI mistaking it for a request body field.
    """
    if not settings.cache_enabled:
        return NullCacheBackend()
    if settings.cache_backend == "sqlite":
        return SqliteCacheBackend(settings.cache_db_path)
    raise ValueError(f"Unsupported cache backend: {settings.cache_backend}")
