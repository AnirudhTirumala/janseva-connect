from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.member import Member
from app.models.scheme import Scheme
from app.models.certificate import Certificate
from app.models.certificate_type import CertificateType
from app.models.application import SchemeApplication
from app.schemas.ai import (
    AIChatRequest, AIChatResponse, AILetterRequest, AIReportRequest, AISQLRequest,
)
from app.routers.certificates import DEFAULT_TYPES
from app.utils.ai_client import ask_ai, ask_ai_with_tools, classify_support_message
from app.utils.ai_tools import (
    active_certificate_type_keys, build_tool_executor, citizen_tool_schemas, parse_tool_arguments,
)
from app.utils.issue_escalation import create_ai_issue

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


def _scheme_documents(scheme: Scheme) -> str:
    """Schemes created today define documents one at a time in the structured
    document_requirements table; the free-text field on Scheme only ever holds
    data from before that change, so it's used as a fallback, not the primary source."""
    if scheme.document_requirements:
        return ", ".join(
            f"{req.name}{'' if req.is_mandatory else ' (optional)'}"
            for req in scheme.document_requirements
        )
    return scheme.required_documents or "not specified"


def _age_from(date_of_birth) -> int | None:
    """Whole years, computed here rather than left to the model - eligibility
    turns on it and a language model doing date arithmetic is a bad idea."""
    if not date_of_birth:
        return None
    today = date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def _household_profile_context(member: Member | None, household_size: int | None) -> str:
    """The citizen's own household record, in the form the assistant needs.

    Without this the assistant knows the scheme catalogue but nothing about
    the person asking, so "what am I eligible for?" can only be answered with
    a list of questions about details the portal already holds - which is
    exactly the runaround the platform exists to remove.

    Deliberately omitted: Aadhaar number, phone, and street address. None of
    them affect eligibility for anything in the catalogue, and this text is
    sent to a third-party model. A national identity number in particular has
    no business leaving the database to answer "can I get a pension?".
    """
    if member is None:
        return (
            "This citizen has NOT completed their household profile yet, so nothing is known "
            "about their age, income, or village. They cannot apply for any scheme, request a "
            "certificate, or raise an issue until they do. If they ask what they are eligible "
            "for, tell them to complete their household profile first - Dashboard -> "
            "Complete my profile - and that everything opens up once it is saved."
        )

    age = _age_from(member.date_of_birth)
    facts = [f"- Name: {member.full_name}"]
    facts.append(f"- Age: {age} years old" if age is not None else "- Age: not recorded in their profile")
    if member.gender:
        facts.append(f"- Gender: {member.gender}")
    location = ", ".join(part for part in (member.village, member.mandal, member.district, member.state) if part)
    facts.append(f"- Lives in: {location or 'not recorded'}")
    facts.append(
        f"- Annual household income: Rs {member.annual_income:,}"
        if member.annual_income is not None
        else "- Annual household income: not recorded in their profile"
    )
    if household_size and household_size > 1:
        facts.append(f"- Household size on record: {household_size} people")

    return (
        "THIS CITIZEN'S HOUSEHOLD RECORD (already on file - do NOT ask them for any of it):\n"
        + "\n".join(facts)
    )


def _known_facts_directive(member: "Member | None", age: int | None) -> str:
    """A short, concrete restatement of what is already known, placed LAST.

    The household record alone was not enough: the model still opened with
    "please confirm your age" even with "Age: 68" sitting in the context, a
    few hundred tokens earlier and surrounded by catalogue text. Naming the
    actual values again immediately before the citizen's message - the
    position a model weights most - is what stops the runaround.
    """
    if member is None:
        return ""
    known = []
    if age is not None:
        known.append(f"they are {age} years old")
    if member.annual_income is not None:
        known.append(f"their annual household income is Rs {member.annual_income:,}")
    place = ", ".join(part for part in (member.village, member.mandal, member.district) if part)
    if place:
        known.append(f"they live in {place}")
    if member.gender:
        known.append(f"their gender is {member.gender}")
    if not known:
        return ""
    return (
        "\n\nFINAL RULE, overriding anything above: you ALREADY KNOW that "
        + "; ".join(known)
        + ". Do not ask the citizen to confirm any of these - state your conclusion using them. "
        "Asking for a detail the portal already holds is the single thing this assistant "
        "must never do."
    )


def _citizen_own_records_context(db: Session, current_user: User, certificate_types: list[CertificateType]) -> str:
    """A citizen's own issued certificates and scheme application statuses -
    without this, the assistant only ever knows the general catalog (what
    certificate types/schemes exist), never what this specific citizen
    already has or applied for, so it can't answer "what certificates were
    issued to me" or "what's my application status" at all."""
    member_ids = [m.id for m in db.query(Member.id).filter(Member.user_id == current_user.id).all()]
    if not member_ids:
        return "This citizen has no linked household/member profile yet, so they have no certificates or applications on file."

    type_names = {c.key: c.name for c in certificate_types}
    certificates = (
        db.query(Certificate)
        .filter(Certificate.member_id.in_([m for m in member_ids]))
        .order_by(Certificate.issued_at.desc())
        .all()
    )
    cert_lines = "\n".join(
        f"- {type_names.get(c.certificate_type, c.certificate_type.replace('-', ' ').title())} "
        f"certificate, number {c.certificate_number}, issued "
        f"{c.issued_at.strftime('%d %b %Y') if c.issued_at else 'recently'}"
        for c in certificates
    ) or "No certificates have been issued to this citizen yet."

    applications = (
        db.query(SchemeApplication)
        .filter(SchemeApplication.member_id.in_([m for m in member_ids]))
        .order_by(SchemeApplication.submitted_at.desc())
        .all()
    )
    app_lines = "\n".join(
        f"- {a.scheme.name if a.scheme else 'Unknown scheme'}: {a.status.replace('_', ' ')}"
        for a in applications
    ) or "This citizen has not applied to any schemes yet."

    return f"Certificates already issued to this citizen:\n{cert_lines}\n\nThis citizen's own scheme applications:\n{app_lines}"


@router.post("/chat", response_model=AIChatResponse)
@limiter.limit("20/minute")
def chat(request: Request, payload: AIChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    General-purpose citizen-facing assistant: explains schemes, eligibility,
    required documents, certificates, and how to apply - answering the FAQ
    staff currently field manually ("what am I eligible for?", "how do I apply?").
    Both catalogs below are queried fresh on every request, so a scheme or
    certificate type an admin just added/edited/removed is reflected immediately,
    with no caching and no restart needed. For a citizen, their own issued
    certificates and application statuses are included too (see
    _citizen_own_records_context) so questions about their own record don't
    get a generic "check the portal" non-answer.

    Before replying, the message is also classified (see
    classify_support_message) for whether it's reporting a problem the
    assistant can't fix itself. If so, a real Issue is logged and the
    right people are notified - a portal/technical bug goes to the state
    and super administrators, an application/service problem goes to every
    staff/admin with jurisdiction over the reporter - and the reply is
    grounded in that real ticket instead of an unbacked "I'll report this".
    """
    # The citizen's own household record, so eligibility can be answered
    # instead of interrogated. Loaded once and reused for the income checks
    # annotated onto each scheme below.
    member = None
    household_size = None
    if current_user.role == "citizen":
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if member:
            head_id = member.family_head_id or member.id
            household_size = (
                db.query(func.count(Member.id))
                .filter((Member.family_head_id == head_id) | (Member.id == head_id))
                .scalar()
            )

    schemes = db.query(Scheme).filter(Scheme.is_active == True).all()  # noqa: E712

    def _income_verdict(scheme: Scheme) -> str:
        """Decide the income test in Python, not in the model.

    It is the one eligibility rule the database can settle exactly, and a
    comparison a language model can plausibly get wrong. Stating the
    verdict keeps the assistant from telling a citizen they qualify for
    something they are over the limit for.
    """
        if member is None or member.annual_income is None or scheme.max_income_limit is None:
            return ""
        if member.annual_income <= scheme.max_income_limit:
            return " [INCOME CHECK: this citizen's income is WITHIN this scheme's limit]"
        return " [INCOME CHECK: this citizen's income is ABOVE this scheme's limit - they do NOT qualify]"

    scheme_context = "\n".join(
        f"- {s.name}: {s.description} (Eligibility: {s.eligibility_criteria or 'not specified'}; "
        f"Max income: {s.max_income_limit or 'no limit'}; Documents: {_scheme_documents(s)})"
        f"{_income_verdict(s)}"
        for s in schemes
    ) or "No schemes currently in the system."

    certificate_types = db.query(CertificateType).filter(CertificateType.is_active == True).all()  # noqa: E712
    certificate_context = "\n".join(
        f"- {c.name} ({c.prefix} prefix): {c.description or 'no description provided'}"
        for c in certificate_types
    ) or "No certificate types currently in the system."

    personal_context = ""
    if current_user.role == "citizen":
        personal_context = f"\n\n{_citizen_own_records_context(db, current_user, certificate_types)}"

    # Try to resolve it in-chat first (the system prompt above already
    # covers that); only escalate to a real, notified ticket when the
    # message is reporting something this assistant genuinely can't fix.
    escalation_note = ""
    classification = classify_support_message(payload.message, payload.history)
    if classification["is_issue"]:
        issue, audience_label = create_ai_issue(
            db, reporter=current_user, category=classification["category"],
            title=classification["title"], description=classification["description"],
        )
        db.commit()
        db.refresh(issue)
        escalation_note = (
            "\n\nIMPORTANT: the message you are replying to has just been logged as support "
            f"ticket #{issue.id} and sent to {audience_label}. In your reply, briefly and "
            f"naturally confirm this happened, mention ticket #{issue.id} so they can refer to "
            "it, and reassure them it will be looked at - but do not invent a specific timeframe."
        )

    system_prompt = (
        "You are the AI assistant for JanSeva Connect, a Smart Community Management Platform for "
        "Andhra Pradesh Panchayat services. You help citizens understand government welfare schemes, "
        "eligibility, required documents, available certificates, and how to use the platform "
        "(registering, applying for schemes, checking status, requesting or downloading certificates). "
        "YOU CAN ACT, not just advise. Two tools are available and they file real records: "
        "request_certificate submits an official certificate request, and raise_issue reports a "
        "problem to the right office. Use them when the citizen asks you to - \"apply for an "
        "income certificate\", \"report that the streetlight is broken\" - rather than telling "
        "them to go and do it themselves on another page.\n"
        "  - A purpose/reason is OPTIONAL on a certificate request. If their message says why "
        "they need it, pass that as purpose. If it does not, file it anyway with no purpose - "
        "the office can review without one. Do NOT invent a reason, and never hold the request "
        "back waiting for an optional field.\n"
        "  - For raise_issue you DO need a usable title and description. If the citizen has only "
        "said \"something is broken\", ask what and where before calling it.\n"
        "  - Never claim you have done something unless the tool actually returned ok. If it "
        "returns an error, tell them exactly what it said - for example that they already have "
        "an active request for that certificate.\n"
        "  - You cannot approve, reject, issue, or cancel anything, and you cannot act for anyone "
        "other than the person you are speaking to. Say so plainly if asked.\n\n"
        "You are given this citizen's own household record below. USE IT. Never ask them for "
        "their age, income, village, mandal, district, or gender - the portal already holds "
        "those and asking again is the runaround this platform exists to remove. Work out "
        "eligibility yourself from what is on file and state the answer directly, scheme by "
        "scheme, saying which they qualify for and which they do not and why. Where a scheme "
        "line carries an [INCOME CHECK] note, that verdict is authoritative - it was computed "
        "from the database, so never contradict it or recompute it yourself. Only ask about "
        "things genuinely NOT on file, and only when they actually decide the answer - for "
        "example the type of house (kutcha or pucca), how long they have lived in the village, "
        "whether they already draw a government pension, or whether a girl child in the "
        "household attends a government school. Ask for those at the end, briefly, and only "
        "the ones that matter for a scheme they might otherwise qualify for.\n\n"
        "Reply in PLAIN TEXT only - the chat window renders exactly what you send, so Markdown "
        "tables, ** bold **, # headings, and HTML tags appear to the citizen as literal symbols. "
        "Use short paragraphs, and where a list helps, one item per line starting with '- '. "
        "Be concise, friendly, and practical. Only reference the schemes and certificate types given "
        "below - do not invent names or rules that are not listed. If asked something outside your "
        "scope (e.g. unrelated to JanSeva Connect services), politely redirect. Never promise to "
        "'report' or 'pass along' a problem yourself - only the ticket confirmation noted below (if "
        "present) is real; do not claim to take any other action you cannot actually perform.\n\n"
        f"Available schemes:\n{scheme_context}\n\n"
        f"Available certificate types:\n{certificate_context}\n\n"
        f"The user you are speaking to is: {current_user.full_name} (role: {current_user.role})."
        f"{personal_context}"
        f"{escalation_note}"
        f"{_known_facts_directive(member, _age_from(member.date_of_birth) if member else None)}"
    )

    # Agentic only for a citizen, and only for the two create-side actions
    # they could already perform themselves. Staff and admins get the plain
    # advisory assistant - an officer's powers (approve, reject, issue,
    # delete) are deliberately not reachable through a chat box.
    if current_user.role != "citizen":
        return AIChatResponse(reply=ask_ai(system_prompt, payload.message, payload.history))

    tools = citizen_tool_schemas(active_certificate_type_keys(db, DEFAULT_TYPES))
    executor = build_tool_executor(db, current_user, background_tasks)

    def run_tool(name: str, raw_arguments: str) -> dict:
        return executor(name, parse_tool_arguments(raw_arguments))

    reply, actions = ask_ai_with_tools(
        system_prompt, payload.message, payload.history, tools, run_tool
    )
    return AIChatResponse(reply=reply)


@router.post("/draft-letter", response_model=AIChatResponse)
@limiter.limit("10/minute")
def draft_letter(
    request: Request,
    payload: AILetterRequest,
    current_user: User = Depends(require_roles("staff", "admin", "citizen")),
):
    """AI drafts an official letter/application - saves staff/citizens from writing from scratch."""
    system_prompt = (
        "You draft short, formal, official letters/applications addressed to a Gram Panchayat office "
        "in India. Use a respectful, formal tone typical of Indian government correspondence. Include "
        "a subject line, salutation, body, and closing. Keep it under 200 words."
    )
    user_message = (
        f"Draft a letter to '{payload.recipient}' from {payload.member_name} regarding: {payload.purpose}. "
        f"Additional context: {payload.extra_context or 'none'}."
    )
    reply = ask_ai(system_prompt, user_message)
    return AIChatResponse(reply=reply)


@router.post("/monthly-report-summary", response_model=AIChatResponse)
@limiter.limit("10/minute")
def monthly_report_summary(
    request: Request,
    payload: AIReportRequest,
    _staff: User = Depends(require_roles("staff", "admin")),
):
    """
    Admin/Staff: turns raw monthly counters into a readable narrative report,
    replacing the hours currently spent manually writing this summary.
    """
    system_prompt = (
        "You write concise, professional monthly administrative report summaries for a Village "
        "Panchayat office, based on the statistics given. Highlight notable trends (e.g. high pending "
        "applications, strong certificate demand) in 3-5 sentences, followed by 2-3 bullet point "
        "recommendations for the office."
    )
    user_message = (
        f"Month: {payload.month}\n"
        f"New members registered: {payload.new_members}\n"
        f"Certificates issued: {payload.certificates_issued}\n"
        f"Scheme applications received: {payload.applications_received}\n"
        f"Applications approved: {payload.applications_approved}\n"
        f"Applications still pending: {payload.applications_pending}\n"
    )
    reply = ask_ai(system_prompt, user_message)
    return AIChatResponse(reply=reply)


@router.post("/generate-sql", response_model=AIChatResponse)
@limiter.limit("10/minute")
def generate_sql(
    request: Request,
    payload: AISQLRequest,
    _admin: User = Depends(require_roles("admin")),
):
    """
    Admin-only: translates a natural-language question into a read-only SQL
    query against this app's schema, to speed up ad-hoc reporting.
    NOTE: this returns SUGGESTED SQL text only - it is not executed
    automatically, so an admin should review it before running it manually.
    """
    schema_context = (
        "Tables:\n"
        "users(id, full_name, email, phone, role[citizen|staff|admin], is_active, created_at)\n"
        "members(id, user_id, full_name, father_or_husband_name, date_of_birth, gender, "
        "aadhaar_number, address, village, mandal, district, state, phone, annual_income, "
        "family_head_id, created_by_staff_id, created_at)\n"
        "schemes(id, name, description, eligibility_criteria, required_documents, "
        "max_income_limit, is_active, created_at)\n"
        "scheme_applications(id, member_id, scheme_id, status[pending|under_review|approved|rejected], "
        "remarks, reviewed_by_id, reviewed_at, submitted_at)\n"
        "certificates(id, member_id, certificate_type[income|residence|birth], certificate_number, "
        "issued_by_id, file_path, issued_at)\n"
    )
    system_prompt = (
        "You write PostgreSQL SELECT queries (read-only, never INSERT/UPDATE/DELETE/DROP) for an "
        "admin dashboard, based only on the schema given. Return the SQL in a code block, with a "
        "one-line explanation above it.\n\n" + schema_context
    )
    reply = ask_ai(system_prompt, payload.question)
    return AIChatResponse(reply=reply)
