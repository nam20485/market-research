"""Deterministic pricing math: condition multiplier + haggle/floor strategy.

All FMV-derived numbers are computed here in Python (not the LLM prompt) so
pricing stays reproducible; the LLM is only responsible for prose.
"""

from app.schemas.research import PricingConfidence, PricingStrategy

_CONDITION_MULTIPLIERS: dict[str, float] = {
    "new": 1.10,
    "like-new": 1.0,
    "good": 0.90,
    "fair": 0.75,
    "poor": 0.60,
}
_DEFAULT_MULTIPLIER = 1.0


def condition_multiplier(condition: str | None) -> float:
    """Look up the pricing multiplier for a free-text condition string.

    Matching is case-insensitive and tolerant of whitespace/underscore
    variants of "like-new" (e.g. "Like New", "like_new"). Unknown or missing
    conditions default to `1.0` (no adjustment).
    """
    if not condition:
        return _DEFAULT_MULTIPLIER
    normalized = "-".join(condition.strip().lower().split())
    normalized = normalized.replace("_", "-")
    return _CONDITION_MULTIPLIERS.get(normalized, _DEFAULT_MULTIPLIER)


def build_pricing_strategy(
    fmv: float,
    *,
    haggle_pct: float,
    floor_pct: float,
    condition: str | None,
    confidence: PricingConfidence,
    currency: str = "USD",
    rationale: str | None = None,
) -> PricingStrategy:
    """Compute the listing price and firm-bottom floor from a fair market value.

    `listing_price = fmv * (1 + haggle_pct) * multiplier` and
    `firm_bottom = fmv * (1 - floor_pct) * multiplier`, where `multiplier`
    comes from `condition_multiplier(condition)`. Money values are rounded
    to 2 decimal places.
    """
    multiplier = condition_multiplier(condition)
    listing_price = fmv * (1 + haggle_pct) * multiplier
    firm_bottom = fmv * (1 - floor_pct) * multiplier
    return PricingStrategy(
        fmv=round(fmv, 2),
        listing_price=round(listing_price, 2),
        firm_bottom=round(firm_bottom, 2),
        currency=currency,
        haggle_pct=haggle_pct,
        floor_pct=floor_pct,
        condition_multiplier=multiplier,
        confidence=confidence,
        rationale=rationale,
    )
