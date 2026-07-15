"""Schemas for the item identification vertical (`POST /api/identify`)."""

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """One turn of the stateless refinement conversation."""

    role: str
    content: str


class CandidateItem(BaseModel):
    """A single candidate match for the item being identified."""

    name: str
    brand: str | None = None
    model: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.0)
    attributes: dict[str, str] = Field(default_factory=dict)
    reasoning: str | None = None


class IdentifyRequest(BaseModel):
    """Non-file portion of an identify request.

    The client resends `known_attributes` and `conversation` accumulated from
    prior turns on every call, since the refinement loop is stateless server-side.
    """

    description: str
    known_attributes: dict[str, str] = Field(default_factory=dict)
    conversation: list[ConversationTurn] = Field(default_factory=list)


class IdentifyResponse(BaseModel):
    """Result of an identify call: candidates plus whether one is locked in."""

    candidates: list[CandidateItem] = Field(default_factory=list)
    locked: bool = False
    locked_item: CandidateItem | None = None
    follow_up_question: str | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)
