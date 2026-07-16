"""Schemas for the market research vertical (`POST /api/research`)."""

from typing import Literal

from pydantic import BaseModel, Field

PricingConfidence = Literal["sold_comps", "asking_price", "unknown"]


class ResearchRequest(BaseModel):
    """The locked item, as identified in the previous stage."""

    item_name: str
    brand: str | None = None
    model: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    condition: str | None = None
    # None means "use the server's configured default".
    haggle_pct: float | None = None
    floor_pct: float | None = None


class SourceLink(BaseModel):
    """A search result link backing the report, so the user can verify it."""

    title: str
    url: str


class PriceRange(BaseModel):
    low: float | None = None
    high: float | None = None
    currency: str = "USD"
    summary: str | None = None


class PricingStrategy(BaseModel):
    """Python-computed pricing derived from fair market value.

    `listing_price` includes haggle room above FMV; `firm_bottom` is the
    floor below FMV the seller should not go under. Both are adjusted by
    `condition_multiplier`.
    """

    fmv: float
    listing_price: float
    firm_bottom: float
    currency: str = "USD"
    haggle_pct: float
    floor_pct: float
    condition_multiplier: float
    confidence: PricingConfidence
    rationale: str | None = None


class ResearchResponse(BaseModel):
    """Structured market research report. Top-level shape is part of the API contract."""

    price_range: PriceRange
    demand: str
    marketing_angle: str
    sources: list[SourceLink] = Field(default_factory=list)
    pricing: PricingStrategy
