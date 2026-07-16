"""Profiles, prompt builder, temp-image handling, and `/api/post/*` endpoint tests.

`open_browser_session` / `fill` are mocked throughout — no real Chrome/MCP
process is ever spawned by these tests.
"""

import io
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.posting import _save_temp_images
from app.config import Settings, get_settings
from app.main import app
from app.prompts.posting import build_posting_system_prompt
from app.services.posting.profiles import (
    FACEBOOK_MARKETPLACE_PROFILE,
    get_profile,
    list_profiles,
)

client = TestClient(app)


class _FakeUploadFile:
    """Minimal stand-in for FastAPI's `UploadFile` for unit-testing helpers."""

    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class _RaisingSession:
    """Fake async context manager whose `__aenter__` always raises."""

    async def __aenter__(self) -> None:
        raise RuntimeError("chrome not reachable")

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _fake_open_browser_session_factory(fake_session: str = "fake-session"):
    @asynccontextmanager
    async def _fake(settings: Settings | None = None):
        yield fake_session

    return _fake


# ── Profile registry ──────────────────────────────────────────────────────


def test_get_profile_returns_registered_facebook_marketplace() -> None:
    profile = get_profile("facebook_marketplace")
    assert profile is not None
    assert profile is FACEBOOK_MARKETPLACE_PROFILE
    assert profile.label == "Facebook Marketplace"
    assert profile.create_url == "https://www.facebook.com/marketplace/create/item"
    assert "Publish" in profile.fill_instructions


def test_get_profile_returns_none_for_unregistered_marketplace() -> None:
    assert get_profile("craigslist") is None


def test_list_profiles_includes_facebook_marketplace() -> None:
    ids = [profile.id for profile in list_profiles()]
    assert "facebook_marketplace" in ids


# ── Prompt builder ─────────────────────────────────────────────────────────


def test_build_posting_system_prompt_includes_listing_fields() -> None:
    prompt = build_posting_system_prompt(
        FACEBOOK_MARKETPLACE_PROFILE,
        title="Vintage lamp",
        description="Great condition, works well",
        price=42.5,
        image_paths=["/tmp/a.jpg", "/tmp/b.jpg"],
    )
    assert "Vintage lamp" in prompt
    assert "Great condition, works well" in prompt
    assert "42.5" in prompt
    assert "/tmp/a.jpg" in prompt
    assert "/tmp/b.jpg" in prompt
    assert FACEBOOK_MARKETPLACE_PROFILE.create_url in prompt
    assert "Publish" in prompt


def test_build_posting_system_prompt_handles_missing_price_and_images() -> None:
    prompt = build_posting_system_prompt(
        FACEBOOK_MARKETPLACE_PROFILE,
        title="T",
        description="D",
        price=None,
        image_paths=[],
    )
    assert "not provided" in prompt
    assert "(none provided)" in prompt


# ── Temp-image handling ────────────────────────────────────────────────────


async def test_save_temp_images_writes_files_and_skips_missing_filename(tmp_path: Path) -> None:
    images = [
        _FakeUploadFile("a.jpg", b"AAA"),
        _FakeUploadFile("", b"skip-me"),
        _FakeUploadFile("b.png", b"BBB"),
    ]

    paths = await _save_temp_images(images, tmp_path)  # type: ignore[arg-type]

    assert len(paths) == 2
    assert Path(paths[0]).read_bytes() == b"AAA"
    assert Path(paths[0]).suffix == ".jpg"
    assert Path(paths[1]).read_bytes() == b"BBB"


async def test_save_temp_images_defaults_suffix_when_missing(tmp_path: Path) -> None:
    images = [_FakeUploadFile("no-extension", b"XYZ")]
    paths = await _save_temp_images(images, tmp_path)  # type: ignore[arg-type]
    assert Path(paths[0]).suffix == ".jpg"


# ── /api/post/capabilities ─────────────────────────────────────────────────


def test_capabilities_endpoint_lists_marketplaces_when_enabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(posting_enabled=True)
    try:
        response = client.get("/api/post/capabilities")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert {"id": "facebook_marketplace", "label": "Facebook Marketplace"} in body[
        "marketplaces"
    ]


def test_capabilities_endpoint_returns_no_marketplaces_when_disabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(posting_enabled=False)
    try:
        response = client.get("/api/post/capabilities")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json() == {"enabled": False, "marketplaces": []}


# ── /api/post/fill ──────────────────────────────────────────────────────────


def test_fill_endpoint_happy_path_returns_step_summary() -> None:
    fake_run_fill = AsyncMock(return_value=["navigate_page: ok", "fill: ok"])
    with (
        patch("app.api.posting.open_browser_session", _fake_open_browser_session_factory()),
        patch("app.api.posting.run_fill", fake_run_fill),
    ):
        response = client.post(
            "/api/post/fill",
            data={
                "marketplace": "facebook_marketplace",
                "title": "Lamp",
                "description": "Nice lamp",
                "price": "25.5",
            },
            files={"images": ("photo.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "filled"
    assert body["steps_summary"] == ["navigate_page: ok", "fill: ok"]
    fake_run_fill.assert_awaited_once()


def test_fill_endpoint_passes_parsed_fields_and_saved_image_paths_to_fill() -> None:
    captured: dict[str, object] = {}

    async def _capturing_fill(
        session, profile, *, title, description, price, image_paths, settings
    ):
        captured["session"] = session
        captured["profile_id"] = profile.id
        captured["title"] = title
        captured["description"] = description
        captured["price"] = price
        captured["image_bytes"] = [Path(p).read_bytes() for p in image_paths]
        return ["ok"]

    with (
        patch("app.api.posting.open_browser_session", _fake_open_browser_session_factory()),
        patch("app.api.posting.run_fill", _capturing_fill),
    ):
        response = client.post(
            "/api/post/fill",
            data={
                "marketplace": "facebook_marketplace",
                "title": "Lamp",
                "description": "Nice lamp",
            },
            files={"images": ("photo.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")},
        )

    assert response.status_code == 200
    assert captured["session"] == "fake-session"
    assert captured["profile_id"] == "facebook_marketplace"
    assert captured["title"] == "Lamp"
    assert captured["description"] == "Nice lamp"
    assert captured["price"] is None
    assert captured["image_bytes"] == [b"fake-bytes"]


def test_fill_endpoint_unknown_marketplace_returns_400() -> None:
    response = client.post(
        "/api/post/fill",
        data={"marketplace": "craigslist", "title": "T", "description": "D"},
    )
    assert response.status_code == 400


def test_fill_endpoint_returns_400_when_posting_disabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(posting_enabled=False)
    try:
        response = client.post(
            "/api/post/fill",
            data={"marketplace": "facebook_marketplace", "title": "T", "description": "D"},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == 400


def test_fill_endpoint_returns_502_when_browser_session_fails() -> None:
    with patch("app.api.posting.open_browser_session", lambda settings=None: _RaisingSession()):
        response = client.post(
            "/api/post/fill",
            data={"marketplace": "facebook_marketplace", "title": "T", "description": "D"},
        )
    assert response.status_code == 502
    assert "chrome" in response.json()["detail"].lower()


def test_fill_endpoint_returns_502_when_fill_raises() -> None:
    with (
        patch("app.api.posting.open_browser_session", _fake_open_browser_session_factory()),
        patch("app.api.posting.run_fill", AsyncMock(side_effect=RuntimeError("model error"))),
    ):
        response = client.post(
            "/api/post/fill",
            data={"marketplace": "facebook_marketplace", "title": "T", "description": "D"},
        )
    assert response.status_code == 502
