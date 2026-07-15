"""`POST /api/identify` — item identification from description + photos."""

import base64
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.schemas.identify import ConversationTurn, IdentifyRequest, IdentifyResponse
from app.services.identification import IdentificationService
from app.services.llm import LLMService, get_llm_service
from app.services.search import SearchProvider, get_search_provider

router = APIRouter(tags=["identify"])


def get_identification_service(
    llm: LLMService = Depends(get_llm_service),
    search_provider: SearchProvider = Depends(get_search_provider),
) -> IdentificationService:
    return IdentificationService(llm, search_provider)


@router.post("/identify", response_model=IdentifyResponse)
async def identify_item(
    description: str = Form(...),
    known_attributes: str = Form(default="{}"),
    conversation: str = Form(default="[]"),
    images: list[UploadFile] = File(default=[]),
    service: IdentificationService = Depends(get_identification_service),
) -> IdentifyResponse:
    request = IdentifyRequest(
        description=description,
        known_attributes=json.loads(known_attributes),
        conversation=[ConversationTurn(**turn) for turn in json.loads(conversation)],
    )
    image_data_urls = [await _to_data_url(image) for image in images if image.filename]
    return await service.identify(request, image_data_urls=image_data_urls)


async def _to_data_url(image: UploadFile) -> str:
    content = await image.read()
    encoded = base64.b64encode(content).decode("ascii")
    content_type = image.content_type or "image/jpeg"
    return f"data:{content_type};base64,{encoded}"
