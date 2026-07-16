import json
from unittest.mock import AsyncMock

from app.schemas.identify import IdentifyRequest
from app.services.identification import IdentificationService
from app.services.search import SearchResult


def _service(vision_return: str, search_return: list[SearchResult] | None = None) -> tuple[
    IdentificationService, AsyncMock, AsyncMock
]:
    llm = AsyncMock()
    llm.vision = AsyncMock(return_value=vision_return)
    search = AsyncMock()
    search.search = AsyncMock(return_value=search_return or [])
    return IdentificationService(llm, search), llm, search


async def test_identify_locks_on_high_confidence_candidate() -> None:
    payload = {
        "candidates": [
            {"name": "iPhone 13", "brand": "Apple", "model": "A2482", "confidence": 0.95}
        ],
        "locked": True,
        "follow_up_question": None,
    }
    service, llm, search = _service(json.dumps(payload))

    request = IdentifyRequest(description="It's a blue iPhone")
    response = await service.identify(request, image_data_urls=["data:image/jpeg;base64,abc"])

    assert response.locked is True
    assert response.locked_item is not None
    assert response.locked_item.name == "iPhone 13"
    assert response.candidates[0].confidence == 0.95
    assert len(response.conversation) == 1
    assert response.conversation[0].content == "It's a blue iPhone"
    llm.vision.assert_awaited_once()
    search.search.assert_not_awaited()


async def test_identify_locks_on_high_confidence_even_if_llm_says_unlocked() -> None:
    """Regression test: confidence >= LOCK_CONFIDENCE_THRESHOLD must force locked=True
    even when the LLM's own `locked` field says False."""
    payload = {
        "candidates": [
            {"name": "iPhone 13", "brand": "Apple", "model": "A2482", "confidence": 0.95}
        ],
        "locked": False,
        "follow_up_question": None,
    }
    service, llm, search = _service(json.dumps(payload))

    request = IdentifyRequest(description="It's a blue iPhone")
    response = await service.identify(request, image_data_urls=["data:image/jpeg;base64,abc"])

    assert response.locked is True
    assert response.locked_item is not None
    assert response.locked_item.name == "iPhone 13"
    search.search.assert_not_awaited()


async def test_identify_uses_search_when_not_locked() -> None:
    payload = {
        "candidates": [{"name": "Running shoes", "brand": "Brand X", "confidence": 0.4}],
        "locked": False,
        "follow_up_question": "What color are they?",
    }
    search_results = [
        SearchResult(title="Brand X shoes", url="https://example.com", snippet="info")
    ]
    service, llm, search = _service(json.dumps(payload), search_results)

    request = IdentifyRequest(description="Some running shoes")
    response = await service.identify(request)

    assert response.locked is False
    assert response.follow_up_question == "What color are they?"
    search.search.assert_awaited_once()
    assert "search_matches" in response.candidates[0].attributes


async def test_identify_handles_non_json_llm_response_gracefully() -> None:
    service, llm, search = _service("not valid json at all")

    request = IdentifyRequest(description="mystery item")
    response = await service.identify(request)

    assert response.candidates == []
    assert response.locked is False
