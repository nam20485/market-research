"""Prompt templates for the marketplace auto-fill posting vertical."""

from app.services.posting.profiles import MarketplaceProfile

POSTING_SYSTEM_PROMPT = """You are a careful browser-automation agent filling out a marketplace \
listing form on behalf of a human seller, using the provided browser tools.

Marketplace: {label}
Create-listing URL: {create_url}

{fill_instructions}

Listing content to fill in:
- Title: {title}
- Description: {description}
- Price: {price}
- Local photo file paths to upload (if any): {image_paths}

Work step by step: inspect the current page (snapshot or screenshot) before acting, \
use the browser tools to navigate/fill/upload, and re-inspect after significant \
actions to confirm they took effect. Only use the tools made available to you.

When every field above has been filled (or you have done as much as the page allows), \
respond with a final plain-text message summarizing what was filled and STOP — do not \
call any more tools, and never click Publish, Post, Next, or any other submission button.
"""


def build_posting_system_prompt(
    profile: MarketplaceProfile,
    *,
    title: str,
    description: str,
    price: float | None,
    image_paths: list[str],
) -> str:
    """Build the system prompt driving the agent's fill loop for one marketplace."""
    return POSTING_SYSTEM_PROMPT.format(
        label=profile.label,
        create_url=profile.create_url,
        fill_instructions=profile.fill_instructions,
        title=title,
        description=description,
        price=price if price is not None else "(not provided — leave blank for the user)",
        image_paths=", ".join(image_paths) if image_paths else "(none provided)",
    )
