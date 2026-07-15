"""Prompt templates for the item identification vertical."""

IDENTIFY_INSTRUCTIONS = """You are an expert at identifying used items for resale from photos \
and descriptions.

Given the user's description, any attached photos, previously known attributes, and prior
conversation turns, identify the specific item (brand, model, notable attributes).

Respond with ONLY a JSON object of this exact shape, no markdown fences, no extra text:
{{
  "candidates": [
    {{
      "name": "short human-readable item name",
      "brand": "brand or null",
      "model": "model or null",
      "confidence": 0.0-1.0,
      "attributes": {{"key": "value"}},
      "reasoning": "brief reasoning"
    }}
  ],
  "locked": true|false,
  "follow_up_question": "a clarifying question to ask the user, or null if locked"
}}

Set "locked" to true only when you are confident (roughly >= 0.8) about a single top candidate.
List candidates ordered from most to least likely. Ask a specific, targeted follow-up question
when not locked (e.g. about model markings, size, color, distinguishing features).

Known attributes so far: {known_attributes}
Prior conversation: {conversation}
User's latest description: {description}
"""


def build_identify_prompt(
    *,
    description: str,
    known_attributes: dict[str, str],
    conversation: list[str],
) -> str:
    return IDENTIFY_INSTRUCTIONS.format(
        known_attributes=known_attributes or "none",
        conversation=conversation or "none",
        description=description,
    )
