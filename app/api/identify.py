"""`POST /api/identify` — item identification from description + photos."""

import base64
import json
import time

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.logging_config import get_logger
from app.schemas.identify import ConversationTurn, IdentifyRequest, IdentifyResponse
from app.services.identification import IdentificationService
from app.services.llm import LLMService, get_llm_service
from app.services.search import SearchProvider, get_search_provider

router = APIRouter(tags=["identify"])
logger = get_logger(__name__)


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
    started = time.perf_counter()
    request = IdentifyRequest(
        description=description,
        known_attributes=json.loads(known_attributes),
        conversation=[ConversationTurn(**turn) for turn in json.loads(conversation)],
    )
    image_data_urls = [await _to_data_url(image) for image in images if image.filename]
    logger.info(
        "identify request: desc_len=%d images=%d conversation_turns=%d",
        len(description),
        len(image_data_urls),
        len(request.conversation),
    )
    try:
        response = await service.identify(request, image_data_urls=image_data_urls)
    except Exception:
        logger.exception("identify failed after %.2fs", time.perf_counter() - started)
        raise
    logger.info(
        "identify complete in %.2fs: candidates=%d locked=%s",
        time.perf_counter() - started,
        len(response.candidates),
        response.locked,
    )
    return response


async def _to_data_url(image: UploadFile) -> str:
    content = await image.read()
    encoded = base64.b64encode(content).decode("ascii")
    content_type = image.content_type or "image/jpeg"
    return f"data:{content_type};base64,{encoded}"
