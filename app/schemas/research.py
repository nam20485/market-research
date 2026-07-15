"""Schemas for the market research vertical (`POST /api/research`)."""

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """The locked item, as identified in the previous stage."""

    item_name: str
    brand: str | None = None
    model: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    condition: str | None = None


class SourceLink(BaseModel):
    """A search result link backing the report, so the user can verify it."""

    title: str
    url: str


class PriceRange(BaseModel):
    low: float | None = None
    high: float | None = None
    currency: str = "USD"
    summary: str | None = None


class ResearchResponse(BaseModel):
    """Structured market research report. Top-level shape is part of the API contract."""

    price_range: PriceRange
    demand: str
    marketing_angle: str
    sources: list[SourceLink] = Field(default_factory=list)
