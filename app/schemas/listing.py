"""Schemas for the listing generation vertical (`POST /api/listing`)."""

from pydantic import BaseModel, Field


class ListingRequest(BaseModel):
    """The locked item plus research context, gated on the user approving the report."""

    item_name: str
    brand: str | None = None
    model: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    condition: str | None = None
    price: float | None = None
    research_summary: str | None = None
    research_approved: bool = False


class MarketplaceListing(BaseModel):
    title: str = ""
    description: str = ""


class ListingResponse(BaseModel):
    """Copy-paste-ready listing content per marketplace."""

    facebook_marketplace: MarketplaceListing
    offerup: MarketplaceListing
