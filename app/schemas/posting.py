"""Schemas for the marketplace auto-fill posting vertical (`/api/post/*`).

`POST /api/post/fill` itself arrives as a multipart form (so listing photos can
be attached as files), so it has no dedicated request schema here — its fields
are declared directly on the route in `app/api/posting.py`.
"""

from typing import Literal

from pydantic import BaseModel, Field


class MarketplaceInfo(BaseModel):
    """A single marketplace auto-fill profile exposed to the frontend."""

    id: str
    label: str


class PostingCapabilities(BaseModel):
    """Whether marketplace auto-fill is available, and which marketplaces support it."""

    enabled: bool
    marketplaces: list[MarketplaceInfo] = Field(default_factory=list)


class FillResponse(BaseModel):
    """Result of a fill attempt. The agent always stops before Publish/Post."""

    status: Literal["filled"]
    steps_summary: list[str] = Field(default_factory=list)
    screenshot: str | None = None
