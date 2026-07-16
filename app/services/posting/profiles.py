"""Marketplace-agnostic posting profiles for the auto-fill agent.

Each `MarketplaceProfile` describes one marketplace's create-listing form:
where to find it and how the agent should fill it. Facebook Marketplace is
the first profile; OfferUp is a documented future addition (see
docs/fb_marketplace_auto-fill_caf2840d.plan.md's "Phase 2 note").
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketplaceProfile:
    """Everything the agent needs to fill one marketplace's listing form."""

    id: str
    label: str
    create_url: str
    fill_instructions: str
    field_hints: dict[str, str] = field(default_factory=dict)


FACEBOOK_MARKETPLACE_PROFILE = MarketplaceProfile(
    id="facebook_marketplace",
    label="Facebook Marketplace",
    create_url="https://www.facebook.com/marketplace/create/item",
    fill_instructions=(
        "Navigate to the create-item form if you are not already there. Fill the "
        "'Title' field with the listing title and the 'Description' field with the "
        "listing description. Upload every provided local photo file via the photo "
        "upload control. If a price was provided, fill the 'Price' field; otherwise "
        "leave it blank. Leave 'Category' and 'Condition' unset for the user to fill "
        "in themselves. Do NOT click Publish, Post, Next, or any other submission "
        "button — stop as soon as the fields above are filled so the user can review "
        "and submit the listing manually."
    ),
    field_hints={
        "title": "Title",
        "description": "Description",
        "price": "Price",
        "photos": "Add photos",
    },
)

_PROFILES: dict[str, MarketplaceProfile] = {
    FACEBOOK_MARKETPLACE_PROFILE.id: FACEBOOK_MARKETPLACE_PROFILE,
}


def get_profile(marketplace_id: str) -> MarketplaceProfile | None:
    """Look up a registered profile by id, or `None` if unknown."""
    return _PROFILES.get(marketplace_id)


def list_profiles() -> list[MarketplaceProfile]:
    """Return all registered profiles, for the `/api/post/capabilities` response."""
    return list(_PROFILES.values())
