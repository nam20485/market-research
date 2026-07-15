from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.identify import get_identification_service
from app.api.listing import get_listing_service
from app.api.research import get_research_service
from app.main import app
from app.schemas.identify import IdentifyResponse
from app.schemas.listing import ListingResponse, MarketplaceListing
from app.schemas.research import PriceRange, ResearchResponse
from app.services.listing import ResearchNotApprovedError

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_identify_endpoint_returns_service_response() -> None:
    fake_service = AsyncMock()
    fake_service.identify = AsyncMock(
        return_value=IdentifyResponse(
            candidates=[], locked=False, follow_up_question="More detail?"
        )
    )
    app.dependency_overrides[get_identification_service] = lambda: fake_service

    try:
        response = client.post(
            "/api/identify",
            data={"description": "A blue lamp", "known_attributes": "{}", "conversation": "[]"},
        )
    finally:
        app.dependency_overrides.pop(get_identification_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is False
    assert body["follow_up_question"] == "More detail?"
    fake_service.identify.assert_awaited_once()


def test_research_endpoint_returns_service_response() -> None:
    fake_service = AsyncMock()
    fake_service.research = AsyncMock(
        return_value=ResearchResponse(
            price_range=PriceRange(low=10, high=20, summary="$10-$20"),
            demand="Moderate",
            marketing_angle="Highlight durability",
            sources=[],
        )
    )
    app.dependency_overrides[get_research_service] = lambda: fake_service

    try:
        response = client.post("/api/research", json={"item_name": "Widget"})
    finally:
        app.dependency_overrides.pop(get_research_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["price_range"]["summary"] == "$10-$20"
    assert body["demand"] == "Moderate"
    assert body["marketing_angle"] == "Highlight durability"


def test_listing_endpoint_returns_service_response() -> None:
    fake_service = AsyncMock()
    fake_service.generate = AsyncMock(
        return_value=ListingResponse(
            facebook_marketplace=MarketplaceListing(title="FB", description="FB body"),
            offerup=MarketplaceListing(title="OU", description="OU body"),
        )
    )
    app.dependency_overrides[get_listing_service] = lambda: fake_service

    try:
        response = client.post(
            "/api/listing", json={"item_name": "Widget", "research_approved": True}
        )
    finally:
        app.dependency_overrides.pop(get_listing_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["facebook_marketplace"]["title"] == "FB"
    assert body["offerup"]["description"] == "OU body"


def test_listing_endpoint_returns_400_when_not_approved() -> None:
    fake_service = AsyncMock()
    fake_service.generate = AsyncMock(
        side_effect=ResearchNotApprovedError(
            "Listing generation requires an approved market research report."
        )
    )
    app.dependency_overrides[get_listing_service] = lambda: fake_service

    try:
        response = client.post(
            "/api/listing", json={"item_name": "Widget", "research_approved": False}
        )
    finally:
        app.dependency_overrides.pop(get_listing_service, None)

    assert response.status_code == 400
