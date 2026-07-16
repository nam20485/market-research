"""Prompt templates for the marketplace auto-fill posting vertical."""

from app.services.posting.profiles import BACKEND_APPIUM, MarketplaceProfile

POSTING_SYSTEM_PROMPT = """You are a careful {role} filling out a marketplace \
listing form on behalf of a human seller, using the provided {tool_noun}.

Marketplace: {label}
{target_line}

{fill_instructions}

Listing content to fill in:
- Title: {title}
- Description: {description}
- Price: {price}
- Local photo file paths to upload (if any): {image_paths}

Work step by step: inspect the current screen ({inspect_hint}) before acting, \
use the {tool_noun} to navigate/fill/upload, and re-inspect after significant \
actions to confirm they took effect. Only use the tools made available to you.

When every field above has been filled (or you have done as much as the screen allows), \
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
    is_appium = profile.mcp_backend == BACKEND_APPIUM
    role = "mobile-app automation agent" if is_appium else "browser-automation agent"
    tool_noun = "automation tools" if is_appium else "browser tools"
    inspect_hint = "screenshot or page source" if is_appium else "snapshot or screenshot"
    target_line = (
        f"App package: {profile.app_package}"
        if is_appium and profile.app_package
        else f"Create-listing URL: {profile.create_url}"
    )
    return POSTING_SYSTEM_PROMPT.format(
        role=role,
        tool_noun=tool_noun,
        inspect_hint=inspect_hint,
        target_line=target_line,
        label=profile.label,
        fill_instructions=profile.fill_instructions,
        title=title,
        description=description,
        price=price if price is not None else "(not provided — leave blank for the user)",
        image_paths=", ".join(image_paths) if image_paths else "(none provided)",
    )
