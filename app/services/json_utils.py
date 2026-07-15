"""Best-effort JSON extraction from LLM text responses."""

import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse `text` as a JSON object, tolerating extra prose or markdown fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}
