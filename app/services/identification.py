"""Item identification service: vision attribute extraction + stateless refinement."""

from app.logging_config import get_logger
from app.prompts.identify import build_identify_prompt
from app.schemas.identify import CandidateItem, ConversationTurn, IdentifyRequest, IdentifyResponse
from app.services.json_utils import parse_json_object
from app.services.llm import LLMService
from app.services.search import SearchProvider

LOCK_CONFIDENCE_THRESHOLD = 0.8
logger = get_logger(__name__)


class IdentificationService:
    """Extracts and refines candidate item identities from photos + description."""

    def __init__(self, llm: LLMService, search_provider: SearchProvider) -> None:
        self._llm = llm
        self._search = search_provider

    async def identify(
        self,
        request: IdentifyRequest,
        image_data_urls: list[str] | None = None,
    ) -> IdentifyResponse:
        image_count = len(image_data_urls or [])
        logger.info(
            "identify: calling vision (images=%d known_attrs=%d)",
            image_count,
            len(request.known_attributes),
        )
        prompt = build_identify_prompt(
            description=request.description,
            known_attributes=request.known_attributes,
            conversation=[turn.content for turn in request.conversation],
        )
        raw = await self._llm.vision(text=prompt, image_data_urls=image_data_urls)
        parsed = parse_json_object(raw)

        candidates = [CandidateItem(**candidate) for candidate in parsed.get("candidates", [])]
        top_candidate = candidates[0] if candidates else None
        locked = bool(parsed.get("locked", False)) and top_candidate is not None
        if top_candidate and top_candidate.confidence >= LOCK_CONFIDENCE_THRESHOLD:
            locked = True

        if not locked and top_candidate is not None:
            name_or_model = top_candidate.model or top_candidate.name
            query = " ".join(part for part in (top_candidate.brand, name_or_model) if part)
            if query:
                logger.info("identify: enriching top candidate via search query=%r", query)
                results = await self._search.search(query, max_results=3)
                if results:
                    top_candidate.attributes.setdefault(
                        "search_matches", "; ".join(f"{r.title} ({r.url})" for r in results)
                    )

        conversation = [
            *request.conversation,
            ConversationTurn(role="user", content=request.description),
        ]

        logger.info(
            "identify: parsed candidates=%d locked=%s top=%r",
            len(candidates),
            locked,
            top_candidate.name if top_candidate else None,
        )
        return IdentifyResponse(
            candidates=candidates,
            locked=locked,
            locked_item=top_candidate if locked else None,
            follow_up_question=parsed.get("follow_up_question"),
            conversation=conversation,
        )
