"""Marketplace-agnostic posting profiles for the auto-fill agent.

Each `MarketplaceProfile` describes one marketplace's create-listing form:
where to find it and how the agent should fill it. Facebook Marketplace uses
desktop browser automation (chrome-devtools-mcp); OfferUp uses mobile-native
automation (appium-mcp) because OfferUp has no web posting flow.
"""

from dataclasses import dataclass, field

# Identifies which MCP backend drives a profile.
BACKEND_CHROME_DEVTOOLS = "chrome-devtools"
BACKEND_APPIUM = "appium"


@dataclass(frozen=True)
class MarketplaceProfile:
    """Everything the agent needs to fill one marketplace's listing form.

    ``mcp_backend`` selects the MCP server / automation driver:
    ``"chrome-devtools"`` (desktop browser) or ``"appium"`` (Android app).

    ``create_url`` is the create-listing URL for browser profiles and ``""``
    for app-based profiles (which use ``app_package`` instead).
    """

    id: str
    label: str
    create_url: str
    fill_instructions: str
    mcp_backend: str = BACKEND_CHROME_DEVTOOLS
    app_package: str = ""
    field_hints: dict[str, str] = field(default_factory=dict)


FACEBOOK_MARKETPLACE_PROFILE = MarketplaceProfile(
    id="facebook_marketplace",
    label="Facebook Marketplace",
    create_url="https://www.facebook.com/marketplace/create/item",
    mcp_backend=BACKEND_CHROME_DEVTOOLS,
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

OFFERUP_PROFILE = MarketplaceProfile(
    id="offerup",
    label="OfferUp",
    create_url="",
    mcp_backend=BACKEND_APPIUM,
    app_package="com.offerup",
    fill_instructions=(
        "Launch the OfferUp app if it is not already open (use the app-lifecycle "
        "tool). Tap the '+' or 'Sell' button to start creating a new listing. "
        "Add every provided local photo file to the listing. Fill the title field "
        "with the listing title and the description field with the listing "
        "description. If a price was provided, fill the price field; otherwise "
        "leave it blank. Select the most fitting category if one is obvious from "
        "the item. Leave condition as its default for the user to confirm. "
        "Do NOT tap 'Post', 'Publish', 'Sell', 'Done', or any other submission "
        "button — stop as soon as the fields above are filled so the user can "
        "review and submit the listing manually."
    ),
    field_hints={
        "title": "title",
        "description": "description",
        "price": "price",
        "photos": "add photos",
    },
)

_PROFILES: dict[str, MarketplaceProfile] = {
    FACEBOOK_MARKETPLACE_PROFILE.id: FACEBOOK_MARKETPLACE_PROFILE,
    OFFERUP_PROFILE.id: OFFERUP_PROFILE,
}


def get_profile(marketplace_id: str) -> MarketplaceProfile | None:
    """Look up a registered profile by id, or `None` if unknown."""
    return _PROFILES.get(marketplace_id)


def list_profiles() -> list[MarketplaceProfile]:
    """Return all registered profiles, for the `/api/post/capabilities` response."""
    return list(_PROFILES.values())
