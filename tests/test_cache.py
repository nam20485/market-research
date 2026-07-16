import time
from pathlib import Path

import pytest

from app.config import Settings
from app.services.cache import (
    NullCacheBackend,
    SqliteCacheBackend,
    build_cache_key,
    get_cache_backend,
)


async def test_sqlite_cache_set_then_get_roundtrips(tmp_path: Path) -> None:
    backend = SqliteCacheBackend(str(tmp_path / "cache.sqlite3"))

    await backend.set("k1", {"a": 1, "b": [1, 2, 3]}, ttl_seconds=60)
    value = await backend.get("k1")

    assert value == {"a": 1, "b": [1, 2, 3]}


async def test_sqlite_cache_get_missing_key_returns_none(tmp_path: Path) -> None:
    backend = SqliteCacheBackend(str(tmp_path / "cache.sqlite3"))

    assert await backend.get("missing") is None


async def test_sqlite_cache_expires_entries_past_ttl(tmp_path: Path) -> None:
    backend = SqliteCacheBackend(str(tmp_path / "cache.sqlite3"))

    await backend.set("k1", "value", ttl_seconds=-1)
    time.sleep(0.01)

    assert await backend.get("k1") is None


async def test_sqlite_cache_set_overwrites_existing_key(tmp_path: Path) -> None:
    backend = SqliteCacheBackend(str(tmp_path / "cache.sqlite3"))

    await backend.set("k1", "first", ttl_seconds=60)
    await backend.set("k1", "second", ttl_seconds=60)

    assert await backend.get("k1") == "second"


async def test_sqlite_cache_creates_parent_directories(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "cache.sqlite3"

    backend = SqliteCacheBackend(str(db_path))
    await backend.set("k1", "v", ttl_seconds=60)

    assert await backend.get("k1") == "v"


async def test_null_cache_backend_always_returns_none() -> None:
    backend = NullCacheBackend()

    await backend.set("k1", "value", ttl_seconds=60)

    assert await backend.get("k1") is None


def test_build_cache_key_normalizes_case_and_whitespace() -> None:
    key_a = build_cache_key("  Foo   Bar ", kind="sold_comps", schema_version=1)
    key_b = build_cache_key("foo bar", kind="sold_comps", schema_version=1)

    assert key_a == key_b
    assert key_a == "sold_comps:v1:foo bar"


def test_build_cache_key_differs_by_schema_version() -> None:
    key_v1 = build_cache_key("foo", kind="sold_comps", schema_version=1)
    key_v2 = build_cache_key("foo", kind="sold_comps", schema_version=2)

    assert key_v1 != key_v2


def test_build_cache_key_joins_multiple_parts() -> None:
    key = build_cache_key("Acme", "Widget 3000", kind="sold_comps", schema_version=1)

    assert key == "sold_comps:v1:acme widget 3000"


def test_get_cache_backend_returns_null_when_disabled() -> None:
    settings = Settings(cache_enabled=False)
    assert isinstance(get_cache_backend(settings), NullCacheBackend)


def test_get_cache_backend_returns_sqlite_for_default_setting(tmp_path: Path) -> None:
    settings = Settings(
        cache_enabled=True, cache_backend="sqlite", cache_db_path=str(tmp_path / "c.sqlite3")
    )
    assert isinstance(get_cache_backend(settings), SqliteCacheBackend)


def test_get_cache_backend_rejects_unknown_backend() -> None:
    settings = Settings(cache_enabled=True, cache_backend="redis")
    with pytest.raises(ValueError, match="Unsupported cache backend"):
        get_cache_backend(settings)
