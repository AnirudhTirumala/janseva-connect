from typing import Annotated, List, Literal

from pydantic import BaseModel, Field, StringConstraints

# Every field below is bounded. The assistant forwards this text to a paid
# third-party model, so an unbounded `message` or `history` is not just a
# database concern - it is somebody else's bill and an easy way to burn a
# shared API quota from one authenticated account.
ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class AIChatHistoryItem(BaseModel):
    """One prior turn replayed for context.

    The role is constrained to the two values a conversation can contain:
    a client must not be able to inject its own `system` turn and rewrite
    the assistant's instructions from the browser.
    """
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=4000)]


class AIChatRequest(BaseModel):
    message: ChatText
    # Recent conversation context from the frontend, newest last.
    history: List[AIChatHistoryItem] = Field(default_factory=list, max_length=20)


class AIChatResponse(BaseModel):
    reply: str


class AILetterRequest(BaseModel):
    purpose: ChatText          # e.g. "request for road repair", "NOC for bank loan"
    recipient: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] = "The Panchayat Secretary"
    member_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    extra_context: Annotated[str, StringConstraints(max_length=2000)] | None = None


class AIReportRequest(BaseModel):
    # Admin passes raw stats, AI turns it into a readable monthly report narrative
    new_members: int = Field(..., ge=0, le=10_000_000)
    certificates_issued: int = Field(..., ge=0, le=10_000_000)
    applications_received: int = Field(..., ge=0, le=10_000_000)
    applications_approved: int = Field(..., ge=0, le=10_000_000)
    applications_pending: int = Field(..., ge=0, le=10_000_000)
    month: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class AISQLRequest(BaseModel):
    question: ChatText  # natural language, e.g. "how many pending applications per scheme?"
