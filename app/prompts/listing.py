"""Prompt templates for the listing generation vertical."""

LISTING_INSTRUCTIONS = """You are an expert at writing high-converting used-item marketplace \
listings.

Write copy-paste-ready listing content for the item below, tailored separately for Facebook
Marketplace and OfferUp. Facebook Marketplace copy tends to be a bit more conversational;
OfferUp copy tends to be concise and keyword-forward for search. Do not fabricate condition
details beyond what is given.

Respond with ONLY a JSON object of this exact shape, no markdown fences, no extra text:
{{
  "facebook_marketplace": {{"title": "...", "description": "..."}},
  "offerup": {{"title": "...", "description": "..."}}
}}

Item: {item_description}
Condition: {condition}
Asking price: {price}
Market research summary: {research_summary}
"""


def build_listing_prompt(
    *,
    item_description: str,
    condition: str | None,
    price: float | None,
    research_summary: str | None,
) -> str:
    return LISTING_INSTRUCTIONS.format(
        item_description=item_description,
        condition=condition or "unknown",
        price=price if price is not None else "not set",
        research_summary=research_summary or "none provided",
    )
