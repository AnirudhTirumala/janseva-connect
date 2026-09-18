"""The AI assistant acting on a citizen's behalf.

The assistant can now DO two things, not just advise: request a certificate
and raise an issue. That makes it an authorization surface, so most of what
follows is about what it must refuse, not what it can do.
"""

from app.core.security import hash_password
from app.models.member import Member
from app.models.user import User
from tests.conftest import get_auth_header

CITIZEN_PASSWORD = "Citizen#Secure7"


def _citizen(db, email="agent.citizen@example.com", with_profile=True):
    user = User(
        full_name="Ravi Kumar", email=email,
        hashed_password=hash_password(CITIZEN_PASSWORD), role="citizen",
    )
    db.add(user)
    db.commit()
    if with_profile:
        db.add(Member(
            user_id=user.id, full_name="Ravi Kumar", address="5 Temple Street",
            village="Kollur", mandal="Tenali", district="Guntur", annual_income=84000,
        ))
        db.commit()
    return user


def _executor(db, citizen):
    from app.utils.ai_tools import build_tool_executor
    return build_tool_executor(db, citizen, background_tasks=None)


# --- What it can do ----------------------------------------------------------

def test_assistant_files_a_certificate_request(db_session):
    from app.models.certificate_request import CertificateRequest

    citizen = _citizen(db_session)
    result = _executor(db_session, citizen)("request_certificate", {"certificate_type": "income"})

    assert result["ok"] is True, result
    request = db_session.query(CertificateRequest).filter(
        CertificateRequest.id == result["request_id"]).first()
    assert request.certificate_type == "income"
    assert request.requested_by_id == citizen.id
    assert request.status == "pending"


def test_reason_is_optional_so_the_assistant_never_stalls(db_session):
    """Explicitly requested behaviour: purpose is optional, so an assistant
    that withholds the request waiting for one is broken."""
    from app.models.certificate_request import CertificateRequest

    citizen = _citizen(db_session)
    execute = _executor(db_session, citizen)

    without = execute("request_certificate", {"certificate_type": "income"})
    assert without["ok"] is True
    assert db_session.query(CertificateRequest).filter(
        CertificateRequest.id == without["request_id"]).first().purpose is None

    with_reason = execute(
        "request_certificate", {"certificate_type": "residence", "purpose": "Bank loan application"}
    )
    assert with_reason["ok"] is True
    assert db_session.query(CertificateRequest).filter(
        CertificateRequest.id == with_reason["request_id"]).first().purpose == "Bank loan application"


def test_assistant_raises_every_kind_of_issue(db_session):
    from app.models.issue import Issue

    citizen = _citizen(db_session)
    execute = _executor(db_session, citizen)

    for category in ("civic", "application", "portal"):
        result = execute("raise_issue", {
            "category": category, "title": f"A {category} problem",
            "description": "Enough detail for an officer to act on this report.",
        })
        assert result["ok"] is True, result
        issue = db_session.query(Issue).filter(Issue.id == result["issue_id"]).first()
        assert issue.category == category
        assert issue.source == "ai_assistant"   # the trail shows how it arrived
        assert issue.citizen_user_id == citizen.id


# --- What it must refuse -----------------------------------------------------

def test_assistant_obeys_the_same_rules_as_the_form(db_session):
    """The reason tools call services/citizen_actions: a rule the REST
    endpoint enforces must not be bypassable by asking the model instead."""
    citizen = _citizen(db_session)
    execute = _executor(db_session, citizen)

    assert execute("request_certificate", {"certificate_type": "income"})["ok"] is True
    duplicate = execute("request_certificate", {"certificate_type": "income"})
    assert duplicate["ok"] is False
    assert "already have an active request" in duplicate["error"]

    assert execute("request_certificate", {"certificate_type": "dragon-licence"})["ok"] is False


def test_assistant_will_not_act_without_a_household_record(db_session):
    citizen = _citizen(db_session, email="noprofile@example.com", with_profile=False)
    execute = _executor(db_session, citizen)

    certificate = execute("request_certificate", {"certificate_type": "income"})
    assert certificate["ok"] is False
    assert "profile" in certificate["error"].lower()

    issue = execute("raise_issue", {
        "category": "civic", "title": "Broken drain",
        "description": "The drain on the corner is overflowing badly.",
    })
    assert issue["ok"] is False


def test_it_cannot_act_for_anyone_but_the_signed_in_citizen(db_session):
    """Identity is not a tool argument, so an injected instruction has nothing
    to retarget. Extra arguments a model invents are ignored outright."""
    from app.models.certificate_request import CertificateRequest

    victim = _citizen(db_session, email="victim@example.com")
    attacker = _citizen(db_session, email="attacker@example.com")
    attacker_member = db_session.query(Member).filter(Member.user_id == attacker.id).first()

    result = _executor(db_session, attacker)("request_certificate", {
        "certificate_type": "income",
        # All invented by the model / injected prompt text.
        "member_id": 999, "user_id": victim.id, "requested_by_id": victim.id,
        "email": "victim@example.com",
    })
    assert result["ok"] is True
    request = db_session.query(CertificateRequest).filter(
        CertificateRequest.id == result["request_id"]).first()
    assert request.requested_by_id == attacker.id
    assert request.member_id == attacker_member.id


def test_no_tool_exists_for_approving_or_deleting(db_session):
    """Authority is bounded by which tools exist at all - a model cannot call
    a function that was never offered."""
    from app.utils.ai_tools import citizen_tool_schemas

    names = {tool["function"]["name"] for tool in citizen_tool_schemas(["income"])}
    assert names == {"request_certificate", "raise_issue"}
    for forbidden in ("approve", "reject", "delete", "deactivate", "review", "issue_certificate"):
        assert not any(forbidden in name for name in names)


def test_unknown_tool_names_are_rejected(db_session):
    citizen = _citizen(db_session)
    result = _executor(db_session, citizen)("delete_all_certificates", {})
    assert result["ok"] is False
    assert "Unknown action" in result["error"]


def test_staff_get_the_advisory_assistant_with_no_tools(client, db_session, seeded_admin, monkeypatch):
    """An officer's powers must not be reachable through a chat box."""
    import app.routers.ai_assistant as ai_assistant_module

    called = {"with_tools": False, "plain": False}
    monkeypatch.setattr(ai_assistant_module, "classify_support_message",
                        lambda message, history=None: {"is_issue": False, "category": None,
                                                       "title": None, "description": None})

    def plain(system_prompt, message, history=None):
        called["plain"] = True
        return "advice only"

    def with_tools(system_prompt, message, history, tools, execute):
        called["with_tools"] = True
        return "acted", []

    monkeypatch.setattr(ai_assistant_module, "ask_ai", plain)
    monkeypatch.setattr(ai_assistant_module, "ask_ai_with_tools", with_tools)

    headers = get_auth_header(client, seeded_admin.email, "AdminPass123")
    res = client.post("/api/ai/chat", headers=headers, json={"message": "hello", "history": []})
    assert res.status_code == 200
    assert called["plain"] is True
    assert called["with_tools"] is False


# --- Failure handling and traceability ---------------------------------------

def test_certificate_tool_offers_only_types_that_exist(db_session):
    from app.models.certificate_type import CertificateType
    from app.routers.certificates import DEFAULT_TYPES
    from app.utils.ai_tools import active_certificate_type_keys

    db_session.add(CertificateType(key="caste", name="Caste Certificate", prefix="CST", is_active=True))
    db_session.add(CertificateType(key="retired", name="Retired Type", prefix="RET", is_active=False))
    db_session.commit()

    keys = active_certificate_type_keys(db_session, DEFAULT_TYPES)
    assert "income" in keys and "caste" in keys
    assert "retired" not in keys


def test_actions_are_audited_as_ai_performed(db_session):
    """An officer reviewing the trail must be able to tell a request the
    citizen filed from one a language model filed for them."""
    from app.models.audit_event import AuditEvent

    citizen = _citizen(db_session)
    _executor(db_session, citizen)("request_certificate", {"certificate_type": "income"})

    event = db_session.query(AuditEvent).filter(AuditEvent.event_type == "ai_action").first()
    assert event is not None
    assert event.action == "ai_requested_certificate"
    assert event.actor_user_id == citizen.id
    assert event.details["performed_by"] == "ai_assistant"


def test_a_failing_tool_returns_an_explanation_not_an_exception(db_session, monkeypatch):
    """A failure must reach the model as text it can relay, never a 500 - and
    must not leak the underlying error to the citizen."""
    from app.utils import ai_tools

    citizen = _citizen(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("relation certificate_requests does not exist")

    monkeypatch.setattr(ai_tools, "request_certificate_for", boom)
    result = _executor(db_session, citizen)("request_certificate", {"certificate_type": "income"})
    assert result["ok"] is False
    assert "relation certificate_requests" not in result["error"]


def test_tool_arguments_that_are_not_valid_json_are_survivable():
    from app.utils.ai_tools import parse_tool_arguments

    assert parse_tool_arguments('{"certificate_type": "income"}') == {"certificate_type": "income"}
    assert parse_tool_arguments("not json at all") == {}
    assert parse_tool_arguments("[1,2,3]") == {}   # valid JSON, wrong shape
    assert parse_tool_arguments(None) == {}
