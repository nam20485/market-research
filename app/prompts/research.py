"""Prompt templates for the market research vertical."""

RESEARCH_INSTRUCTIONS = """You are an expert resale market analyst.

Given the identified item and the search results below (sold/active comparable listings),
synthesize a market research report. Base your analysis only on the provided search results;
do not invent prices or facts that are not supported by them.

Respond with ONLY a JSON object of this exact shape, no markdown fences, no extra text:
{{
  "price_range": {{
    "low": number, "high": number, "currency": "USD", "summary": "human readable range"
  }},
  "demand": "a short paragraph describing current demand for this item",
  "marketing_angle": "a short paragraph suggesting the best angle to market/sell this item"
}}

Item: {item_description}
Condition: {condition}

Search results (sold/active comps):
{search_results}
"""


def build_research_prompt(
    *,
    item_description: str,
    condition: str | None,
    search_results: list[str],
) -> str:
    formatted_results = "\n".join(f"- {result}" for result in search_results)
    formatted_results = formatted_results or "(no results found)"
    return RESEARCH_INSTRUCTIONS.format(
        item_description=item_description,
        condition=condition or "unknown",
        search_results=formatted_results,
    )
