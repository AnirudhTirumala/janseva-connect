"""The two actions the assistant may actually perform, and their guard rails.

The assistant is agentic for exactly two things a citizen can already do for
themselves: requesting a certificate and raising an issue. Everything else -
approving, rejecting, issuing, deleting, reading somebody else's record -
stays off limits, and the way it stays off limits is that no tool exists for
it. An LLM cannot be talked into calling a function that was never offered.

Three properties worth stating plainly, because they are what make this safe:

* **Identity is not an argument.** No schema below accepts a member id, user
  id, or email. The acting citizen comes from the authenticated request, so
  no amount of prompt injection ("file this for user 7") can retarget it.
* **The rules live elsewhere.** Every tool calls services/citizen_actions,
  the same code the REST forms use. A refusal there - no household profile,
  duplicate request, unknown certificate type - refuses here identically.
* **Failures are returned, not raised.** A refused action comes back to the
  model as an `ok: false` result with the real reason, so the assistant can
  explain it in plain words instead of the request 500ing.
"""

import json
import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.certificate_type import CertificateType
from app.models.user import User
from app.services.citizen_actions import (
    ISSUE_CATEGORIES,
    CitizenActionError,
    raise_issue_for,
    request_certificate_for,
)
from app.utils.audit import log_event

logger = logging.getLogger("panchayat.ai.tools")


def citizen_tool_schemas(available_certificate_types: list[str]) -> list[dict]:
    """OpenAI/Groq tool definitions for the two permitted actions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "request_certificate",
                "description": (
                    "Submit an official certificate request on behalf of the citizen you are "
                    "talking to, against their own household record. Call this only when they "
                    "have clearly asked for a certificate to be requested or applied for. "
                    "A purpose is optional - if they have not given a reason, submit without "
                    "one rather than refusing or stalling."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "certificate_type": {
                            "type": "string",
                            "description": (
                                "The certificate type key, exactly one of: "
                                + ", ".join(available_certificate_types)
                            ),
                            "enum": available_certificate_types,
                        },
                        "purpose": {
                            "type": "string",
                            "description": "Why they need it, in their own words. Omit if not given.",
                        },
                    },
                    "required": ["certificate_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "raise_issue",
                "description": (
                    "Record a problem the citizen is reporting, so the right office sees it. "
                    "Call this only when they have clearly asked for something to be reported "
                    "or raised, and you have enough detail to write a useful title and "
                    "description. Ask for the missing detail first if you do not."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": list(ISSUE_CATEGORIES),
                            "description": (
                                "civic = a problem in their locality (roads, water, sanitation, "
                                "streetlights). application = a stuck or incorrect scheme "
                                "application, certificate, or service delivery. portal = a "
                                "technical fault in this website or app."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": "A short specific title, 4-150 characters.",
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What is wrong, in enough detail for an officer to act. "
                                "For a civic issue include the location."
                            ),
                        },
                    },
                    "required": ["category", "title", "description"],
                },
            },
        },
    ]


def active_certificate_type_keys(db: Session, builtin_defaults: list[dict]) -> list[str]:
    """Keys the citizen may actually request right now.

    Passed to the model as an enum so it cannot invent a certificate type that
    does not exist, and so a type an admin deactivated stops being offered.
    """
    custom = db.query(CertificateType).filter(CertificateType.is_active == True).all()  # noqa: E712
    custom_keys = [item.key for item in custom]
    all_custom = {item.key for item in db.query(CertificateType).all()}
    builtin_keys = [item["key"] for item in builtin_defaults if item["key"] not in all_custom]
    return builtin_keys + custom_keys


def build_tool_executor(db: Session, citizen: User, background_tasks) -> Callable[[str, dict], dict]:
    """Return a function that performs one named tool call for this citizen.

    The returned callable closes over the authenticated citizen, which is why
    no tool schema needs - or accepts - an identity argument.
    """

    def execute(name: str, arguments: dict) -> dict[str, Any]:
        try:
            if name == "request_certificate":
                request = request_certificate_for(
                    db, citizen,
                    certificate_type=str(arguments.get("certificate_type", "")),
                    purpose=arguments.get("purpose"),
                    background_tasks=background_tasks,
                )
                _audit(db, citizen, "ai_requested_certificate", "certificate_request", request.id,
                       {"certificate_type": request.certificate_type})
                return {
                    "ok": True,
                    "request_id": request.id,
                    "certificate_type": request.certificate_type,
                    "purpose_recorded": request.purpose,
                    "status": request.status,
                    "message": "The certificate request has been filed and the office notified.",
                }

            if name == "raise_issue":
                issue = raise_issue_for(
                    db, citizen,
                    title=str(arguments.get("title", "")),
                    description=str(arguments.get("description", "")),
                    category=str(arguments.get("category", "civic")),
                    # Recorded as assistant-raised so the audit trail and the
                    # Issues page show how it arrived.
                    source="ai_assistant",
                    background_tasks=background_tasks,
                )
                _audit(db, citizen, "ai_raised_issue", "issue", issue.id, {"category": issue.category})
                return {
                    "ok": True,
                    "issue_id": issue.id,
                    "category": issue.category,
                    "title": issue.title,
                    "status": issue.status,
                    "message": "The issue has been recorded and the right office notified.",
                }

            return {"ok": False, "error": f"Unknown action '{name}'."}

        except CitizenActionError as exc:
            # A rule said no. The model needs the reason so it can explain it.
            return {"ok": False, "error": exc.message}
        except Exception:
            # Never let a tool failure become a 500 on the chat endpoint.
            logger.exception("AI tool %s failed for user %s", name, citizen.id)
            db.rollback()
            return {
                "ok": False,
                "error": "That could not be completed right now. Please try again from the portal.",
            }

    return execute


def _audit(db: Session, citizen: User, action: str, target_type: str, target_id, details: dict) -> None:
    """Record that the ASSISTANT did this, not the citizen clicking a form.

    Without this an officer reviewing the trail cannot tell a request the
    citizen filed themselves from one a language model filed for them.
    """
    try:
        log_event(
            db, event_type="ai_action", action=action, actor=citizen,
            route="/api/ai/chat", target_type=target_type, target_id=target_id,
            details={**details, "performed_by": "ai_assistant"},
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not write the AI action audit entry for %s", action)


def parse_tool_arguments(raw: str) -> dict:
    """Tool arguments arrive as a JSON string and are not guaranteed valid."""
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}
