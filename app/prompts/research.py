"""Prompt templates for the market research vertical."""

RESEARCH_INSTRUCTIONS = """You are an expert resale market analyst.

Given the identified item, any sold-comps listings, and the search results below, synthesize
a market research report. Base your analysis only on the provided sold comps and search
results; do not invent prices or facts that are not supported by them.

{fmv_instruction}

Respond with ONLY a JSON object of this exact shape, no markdown fences, no extra text:
{{
  "price_range": {{
    "low": number, "high": number, "currency": "USD", "summary": "human readable range"
  }},
  "demand": "a short paragraph describing current demand for this item",
  "marketing_angle": "a short paragraph suggesting the best angle to market/sell it"{fmv_field}
}}

Item: {item_description}
Condition: {condition}

Sold comps (eBay, most relevant first):
{sold_comps}

Search results (asking-price/active listings):
{search_results}
"""

_FMV_INSTRUCTION_WITH_COMPS = (
    "Sold comps are provided above; a fair market value has already been computed from them "
    "in Python, so do NOT estimate or include an FMV number yourself."
)
_FMV_INSTRUCTION_NO_COMPS = (
    "No sold comps were found. Estimate a fair market value (FMV) in USD from the search "
    'results below and include it as a top-level "estimated_fmv" number in your JSON response. '
    "If the search results give no usable pricing signal, omit the field entirely rather than "
    "guessing."
)
_FMV_FIELD_NO_COMPS = ',\n  "estimated_fmv": number  // your best-guess FMV in USD'


def build_research_prompt(
    *,
    item_description: str,
    condition: str | None,
    sold_comps: list[str],
    search_results: list[str],
) -> str:
    """Build the research synthesis prompt.

    `sold_comps` and `search_results` are pre-formatted lines (e.g.
    `"title: $price (url)"` and `"title: snippet (url)"` respectively).
    When `sold_comps` is empty, the prompt asks the model to additionally
    estimate an FMV number that the Python fallback path can read back out
    of the parsed JSON.
    """
    has_comps = bool(sold_comps)
    formatted_comps = "\n".join(f"- {comp}" for comp in sold_comps) or "(no sold comps found)"
    formatted_results = "\n".join(f"- {result}" for result in search_results)
    formatted_results = formatted_results or "(no results found)"
    return RESEARCH_INSTRUCTIONS.format(
        fmv_instruction=_FMV_INSTRUCTION_WITH_COMPS if has_comps else _FMV_INSTRUCTION_NO_COMPS,
        fmv_field="" if has_comps else _FMV_FIELD_NO_COMPS,
        item_description=item_description,
        condition=condition or "unknown",
        sold_comps=formatted_comps,
        search_results=formatted_results,
    )
