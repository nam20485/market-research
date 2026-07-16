"""Contract tests: Pydantic models and OpenAPI shapes for the public API."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.identify import get_identification_service
from app.api.listing import get_listing_service
from app.api.research import get_research_service
from app.main import app
from app.schemas.identify import (
    CandidateItem,
    ConversationTurn,
    IdentifyRequest,
    IdentifyResponse,
)
from app.schemas.listing import ListingRequest, ListingResponse, MarketplaceListing
from app.schemas.research import (
    PriceRange,
    PricingStrategy,
    ResearchRequest,
    ResearchResponse,
    SourceLink,
)

client = TestClient(app)

# Payload shapes the frontend api.js is expected to send after mapping.
FRONTEND_RESEARCH_BODY = {
    "item_name": "Herman Miller Aeron",
    "brand": "Herman Miller",
    "model": "Aeron",
    "attributes": {"size": "B", "color": "graphite"},
    "condition": "good",
}

FRONTEND_LISTING_BODY = {
    **FRONTEND_RESEARCH_BODY,
    "research_approved": True,
    "research_summary": "Price: $400-$600. Demand: High. Angle: Ergonomic classic",
}

FAKE_PRICING = PricingStrategy(
    fmv=450.0,
    listing_price=517.5,
    firm_bottom=405.0,
    haggle_pct=0.15,
    floor_pct=0.10,
    condition_multiplier=1.0,
    confidence="sold_comps",
)


def test_openapi_documents_all_public_routes() -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/healthz" in paths
    assert "/api/identify" in paths
    assert "/api/research" in paths
    assert "/api/listing" in paths
    assert "/api/post/capabilities" in paths
    assert "/api/post/fill" in paths
    assert "post" in paths["/api/identify"]
    assert "post" in paths["/api/research"]
    assert "post" in paths["/api/listing"]
    assert "get" in paths["/api/post/capabilities"]
    assert "post" in paths["/api/post/fill"]


def test_openapi_registers_core_model_schemas() -> None:
    components = client.get("/openapi.json").json()["components"]["schemas"]
    for name in (
        "CandidateItem",
        "IdentifyResponse",
        "ResearchRequest",
        "ResearchResponse",
        "PriceRange",
        "PricingStrategy",
        "SourceLink",
        "ListingRequest",
        "ListingResponse",
        "MarketplaceListing",
        "PostingCapabilities",
        "FillResponse",
        "MarketplaceInfo",
    ):
        assert name in components, f"missing OpenAPI schema: {name}"


def test_identify_models_round_trip() -> None:
    request = IdentifyRequest(
        description="black office chair",
        known_attributes={"color": "black"},
        conversation=[ConversationTurn(role="user", content="black office chair")],
    )
    assert request.model_dump()["known_attributes"]["color"] == "black"

    candidate = CandidateItem(
        name="Herman Miller Aeron",
        brand="Herman Miller",
        model="Aeron",
        confidence=0.92,
        attributes={"size": "B"},
        reasoning="Mesh back matches Aeron",
    )
    response = IdentifyResponse(
        candidates=[candidate],
        locked=True,
        locked_item=candidate,
        follow_up_question=None,
        conversation=request.conversation,
    )
    reloaded = IdentifyResponse.model_validate(response.model_dump())
    assert reloaded.locked_item is not None
    assert reloaded.locked_item.name == "Herman Miller Aeron"
    assert reloaded.candidates[0].confidence == 0.92


def test_research_models_round_trip() -> None:
    request = ResearchRequest.model_validate(FRONTEND_RESEARCH_BODY)
    assert request.item_name == "Herman Miller Aeron"
    assert request.attributes["size"] == "B"
    assert request.haggle_pct is None
    assert request.floor_pct is None

    response = ResearchResponse(
        price_range=PriceRange(low=400, high=600, currency="USD", summary="$400-$600"),
        demand="High",
        marketing_angle="Ergonomic classic",
        sources=[SourceLink(title="Comp", url="https://example.com/a")],
        pricing=FAKE_PRICING,
    )
    reloaded = ResearchResponse.model_validate(response.model_dump())
    assert reloaded.price_range.low == 400
    assert reloaded.sources[0].url == "https://example.com/a"
    assert reloaded.pricing.listing_price == 517.5
    assert reloaded.pricing.confidence == "sold_comps"


def test_research_request_accepts_explicit_haggle_and_floor_overrides() -> None:
    request = ResearchRequest.model_validate(
        {**FRONTEND_RESEARCH_BODY, "haggle_pct": 0.2, "floor_pct": 0.05}
    )
    assert request.haggle_pct == 0.2
    assert request.floor_pct == 0.05


def test_pricing_strategy_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        PricingStrategy.model_validate(
            {
                "fmv": 10.0,
                "listing_price": 11.0,
                "firm_bottom": 9.0,
                "haggle_pct": 0.1,
                "floor_pct": 0.1,
                "condition_multiplier": 1.0,
                "confidence": "maybe",
            }
        )


def test_listing_models_round_trip() -> None:
    request = ListingRequest.model_validate(FRONTEND_LISTING_BODY)
    assert request.research_approved is True
    assert request.research_summary is not None

    response = ListingResponse(
        facebook_marketplace=MarketplaceListing(title="FB", description="FB body"),
        offerup=MarketplaceListing(title="OU", description="OU body"),
    )
    reloaded = ListingResponse.model_validate(response.model_dump())
    assert reloaded.facebook_marketplace.title == "FB"
    assert reloaded.offerup.description == "OU body"


def test_candidate_item_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        CandidateItem(name="X", confidence=1.5)


def test_research_request_requires_item_name() -> None:
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate({"brand": "Acme"})


def test_frontend_research_payload_is_accepted_by_endpoint() -> None:
    fake_service = AsyncMock()
    fake_service.research = AsyncMock(
        return_value=ResearchResponse(
            price_range=PriceRange(low=400, high=600, summary="$400-$600"),
            demand="High",
            marketing_angle="Ergonomic classic",
            sources=[SourceLink(title="Comp", url="https://example.com/a")],
            pricing=FAKE_PRICING,
        )
    )
    app.dependency_overrides[get_research_service] = lambda: fake_service
    try:
        response = client.post("/api/research", json=FRONTEND_RESEARCH_BODY)
    finally:
        app.dependency_overrides.pop(get_research_service, None)

    assert response.status_code == 200
    body = response.json()
    ResearchResponse.model_validate(body)
    assert body["price_range"]["currency"] == "USD"
    assert body["sources"][0]["title"] == "Comp"
    assert body["pricing"]["confidence"] == "sold_comps"
    assert body["pricing"]["listing_price"] == 517.5


def test_frontend_listing_payload_is_accepted_by_endpoint() -> None:
    fake_service = AsyncMock()
    fake_service.generate = AsyncMock(
        return_value=ListingResponse(
            facebook_marketplace=MarketplaceListing(title="FB", description="FB body"),
            offerup=MarketplaceListing(title="OU", description="OU body"),
        )
    )
    app.dependency_overrides[get_listing_service] = lambda: fake_service
    try:
        response = client.post("/api/listing", json=FRONTEND_LISTING_BODY)
    finally:
        app.dependency_overrides.pop(get_listing_service, None)

    assert response.status_code == 200
    body = response.json()
    ListingResponse.model_validate(body)
    assert set(body.keys()) == {"facebook_marketplace", "offerup"}


def test_identify_response_contract_shape() -> None:
    fake_service = AsyncMock()
    candidate = CandidateItem(
        name="Widget",
        brand="Acme",
        model="1",
        confidence=0.8,
        attributes={"color": "red"},
    )
    fake_service.identify = AsyncMock(
        return_value=IdentifyResponse(
            candidates=[candidate],
            locked=False,
            locked_item=None,
            follow_up_question="What color is it?",
            conversation=[ConversationTurn(role="assistant", content="What color is it?")],
        )
    )
    app.dependency_overrides[get_identification_service] = lambda: fake_service
    try:
        response = client.post(
            "/api/identify",
            data={
                "description": "a widget",
                "known_attributes": '{"color":"red"}',
                "conversation": '[{"role":"user","content":"a widget"}]',
            },
        )
    finally:
        app.dependency_overrides.pop(get_identification_service, None)

    assert response.status_code == 200
    body = response.json()
    IdentifyResponse.model_validate(body)
    assert body["follow_up_question"] == "What color is it?"
    assert body["candidates"][0]["name"] == "Widget"
