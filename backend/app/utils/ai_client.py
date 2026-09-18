import json
import logging

from groq import Groq
from app.core.config import settings

_client = None
logger = logging.getLogger("panchayat.ai")


# Tool calling makes two sequential model round trips, so the provider's
# default deadline is tight for it - an agentic turn was observed timing out
# where a plain answer would not have. Bounded on both ends deliberately: long
# enough for two calls, short enough that a stuck provider cannot pin a worker
# for minutes while the citizen stares at a spinner.
AI_REQUEST_TIMEOUT_SECONDS = 45.0


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY, timeout=AI_REQUEST_TIMEOUT_SECONDS, max_retries=1)
    return _client


def _history_messages(history) -> list[dict]:
    """Normalise validated history items into Groq's message shape.

    Accepts the Pydantic models the routers pass as well as plain dicts,
    and drops anything that is not a user/assistant turn - a client must
    never be able to smuggle its own `system` message into the prompt.
    """
    messages = []
    for item in history or []:
        role = getattr(item, "role", None) or (item.get("role") if isinstance(item, dict) else None)
        content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else None)
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:4000]})
    return messages


def ask_ai(system_prompt: str, user_message: str, history=None) -> str:
    """
    Thin wrapper around Groq's chat completion API (model set by
    settings.GROQ_MODEL, free tier). Centralizing this here means every AI
    feature - chat, letter drafting, report summaries, SQL suggestions -
    shares one place to change providers/models later.
    """
    if not settings.GROQ_API_KEY:
        return (
            "AI Assistant is not configured yet. Ask the administrator to set "
            "GROQ_API_KEY (free at https://console.groq.com) in the backend .env file."
        )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_history_messages(history))
    messages.append({"role": "user", "content": user_message})

    try:
        client = get_groq_client()
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=800,
        )
        return completion.choices[0].message.content
    except Exception:
        # The raw exception can carry the request URL, model name, and
        # provider-side detail. It belongs in the server log, not in a
        # citizen's chat window.
        logger.exception("AI request failed")
        return "AI Assistant is temporarily unavailable right now. Please try again shortly."


_NO_ISSUE = {"is_issue": False, "category": None, "title": None, "description": None}


# These rules intentionally cover only clear, actionable reports.  They are
# not a replacement for the model's contextual classification when Groq is
# available; they are the safe local fallback for the important case where a
# citizen reports a broken portal while the AI provider is offline or has not
# been configured yet.  A generic "I found a bug" stays a question until the
# citizen gives a useful symptom, which prevents a vague conversation from
# creating a duplicate ticket before the assistant has gathered details.
_PORTAL_SIGNALS = (
    "not updating", "does not update", "doesn't update", "did not update",
    "not changing", "does not change", "didn't change", "not changed",
    "need to refresh", "needed to refresh", "have to refresh", "had to refresh",
    "not working", "does not work", "doesn't work", "won't work", "is broken",
    "upload failed", "failed to upload", "unable to upload", "cannot upload", "can't upload",
    "login failed", "cannot log in", "can't log in", "cannot login", "can't login",
    "error message", "shows an error", "getting an error", "page crashed", "app crashed",
    "button is broken", "button not working", "website issue", "portal issue",
)

_APPLICATION_SIGNALS = (
    "application is stuck", "application stuck", "stuck in pending", "stuck pending",
    "pending for", "no response from", "not received my certificate", "certificate not received",
    "wrong application status", "application status is wrong", "incorrect application status",
    "wrong certificate", "certificate details are wrong", "decision is incorrect",
    "application was incorrectly", "service has not been delivered",
)


def _rule_based_support_message(message: str) -> dict:
    """Recognise a small set of unmistakable support reports without a
    network call.  It deliberately errs on the side of normal questions: the
    assistant can answer "how do I upload a document?" itself, whereas "the
    upload status did not update until I refreshed" needs staff attention."""
    normalized = " ".join((message or "").lower().split())
    if not normalized:
        return dict(_NO_ISSUE)

    if any(signal in normalized for signal in _PORTAL_SIGNALS):
        if "upload" in normalized and ("refresh" in normalized or "updat" in normalized or "chang" in normalized):
            title = "Upload status does not refresh"
        elif "upload" in normalized:
            title = "Document upload is not working"
        elif "login" in normalized or "log in" in normalized:
            title = "Portal login problem reported"
        elif "button" in normalized:
            title = "Portal button is not working"
        else:
            title = "Portal problem reported in chat"
        return {"is_issue": True, "category": "portal", "title": title, "description": message.strip()[:2000]}

    if any(signal in normalized for signal in _APPLICATION_SIGNALS):
        if "certificate" in normalized:
            title = "Certificate service problem reported"
        elif "pending" in normalized or "stuck" in normalized:
            title = "Application appears to be stuck"
        else:
            title = "Application service problem reported"
        return {"is_issue": True, "category": "application", "title": title, "description": message.strip()[:2000]}

    return dict(_NO_ISSUE)


def classify_support_message(message: str, history=None) -> dict:
    """
    Decides whether the citizen/staff message just sent to the assistant is
    REPORTING A PROBLEM the assistant cannot fix itself - a technical bug
    in the portal, or a stuck/incorrect application/certificate/service
    issue - as opposed to an ordinary question the assistant can already
    answer from the scheme/certificate catalog. This is what lets the
    assistant actually log and escalate a real problem instead of only
    replying in-chat with a promise nothing backs up.

    Clear technical/service failures are recognised locally first, so an
    actual report is never dropped merely because the optional AI provider
    is unavailable.  Less obvious messages still use the model when it is
    configured; no API key, a network error, or an invalid response then
    safely falls back to "not an issue" instead of fabricating a ticket.
    """
    local_result = _rule_based_support_message(message)
    if local_result["is_issue"]:
        return local_result

    if not settings.GROQ_API_KEY:
        return dict(_NO_ISSUE)

    system_prompt = (
        "You classify ONE message sent to the JanSeva Connect citizen support assistant. "
        "Decide whether it is REPORTING A PROBLEM the assistant itself cannot fix (a technical "
        "bug/defect in the website or app, OR a stuck/incorrect scheme application, certificate "
        "request, or service delivery issue) - as opposed to an ordinary question the assistant "
        "can already answer (eligibility, required documents, how to use the portal, general "
        "conversation, or a question about something that already went fine).\n\n"
        "Respond with ONLY a JSON object, no other text, in exactly this shape:\n"
        '{"is_issue": true or false, "category": "portal" or "application" or null, '
        '"title": "short 5-8 word title" or null, "description": "one or two factual '
        'sentences summarising the problem" or null}\n\n'
        'category "portal" = a technical bug/defect in the website or app itself (a page or '
        "status not updating, an error message, a broken button or upload, a login problem, etc).\n"
        'category "application" = a problem with a specific scheme application, certificate '
        "request, or service delivery that is NOT a technical bug (e.g. pending too long, "
        "wrong details on record, staff not responding, a decision the citizen disputes).\n"
        "If the message is not reporting a problem at all, set is_issue to false and the other "
        "three fields to null. When unsure whether something is genuinely a reportable problem, "
        "prefer is_issue: false."
    )

    try:
        client = get_groq_client()
        messages = [{"role": "system", "content": system_prompt}]
        # Only recent turns are needed for context on what "this" refers to.
        messages.extend(_history_messages(history)[-4:])
        messages.append({"role": "user", "content": message})
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=250,
            response_format={"type": "json_object"},
        )
        data = json.loads(completion.choices[0].message.content)
    except Exception:
        logger.exception("AI issue classification failed; treating as not-an-issue.")
        return dict(_NO_ISSUE)

    category = data.get("category")
    if category not in ("portal", "application"):
        category = None
    title = (data.get("title") or "").strip()[:150] or None
    description = (data.get("description") or "").strip()[:2000] or None
    if not (data.get("is_issue") and category and title and description):
        return dict(_NO_ISSUE)
    return {"is_issue": True, "category": category, "title": title, "description": description}


# One round of tool calls, then a final answer. Bounded deliberately: an
# unbounded agent loop against a live database is a way to file a hundred
# certificate requests from one sentence, and nothing this assistant does
# needs a second round of planning.
MAX_TOOL_ROUNDS = 2
MAX_TOOL_CALLS_PER_TURN = 3


def ask_ai_with_tools(system_prompt, user_message, history, tools, execute_tool):
    """Chat completion that may call tools, returning (reply, actions_taken).

    `execute_tool(name, arguments) -> dict` performs one call and returns a
    JSON-serialisable result. It is expected to return `{"ok": False, ...}`
    for a refusal rather than raising, so a rule saying no becomes something
    the model can explain instead of an error the citizen sees.

    Falls back to the plain, tool-free reply whenever the provider is not
    configured or errors, so the assistant keeps answering questions even when
    it cannot act.
    """
    if not settings.GROQ_API_KEY:
        return ask_ai(system_prompt, user_message, history), []

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_history_messages(history))
    messages.append({"role": "user", "content": user_message})

    actions: list[dict] = []
    try:
        client = get_groq_client()
        for _ in range(MAX_TOOL_ROUNDS):
            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=900,
            )
            choice = completion.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None)
            if not tool_calls:
                return (choice.content or "").strip(), actions

            # Echo the assistant's tool-call turn back verbatim; the protocol
            # requires every tool result to answer a call in the transcript.
            messages.append({
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            })

            for call in tool_calls[:MAX_TOOL_CALLS_PER_TURN]:
                result = execute_tool(call.function.name, call.function.arguments)
                actions.append({"name": call.function.name, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                })

        # Tool rounds exhausted - ask once more, with tools withheld, so the
        # model has to produce prose instead of another call.
        final = client.chat.completions.create(
            model=settings.GROQ_MODEL, messages=messages, temperature=0.3, max_tokens=900,
        )
        return (final.choices[0].message.content or "").strip(), actions

    except Exception:
        logger.exception("AI tool-calling request failed")
        if actions:
            # Something was actually performed before the failure. Saying
            # "unavailable" would tell the citizen nothing happened when a
            # real record now exists.
            done = [a for a in actions if a["result"].get("ok")]
            if done:
                return (
                    "That has been submitted and the office has been notified. You can see it in "
                    "the portal. (I could not finish writing a longer reply just now.)"
                ), actions
        return "AI Assistant is temporarily unavailable right now. Please try again shortly.", actions
