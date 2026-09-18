"""
Tests for:
  - The AI assistant issue-escalation pipeline (app/utils/issue_escalation.py,
    app/utils/ai_client.classify_support_message, and the /api/ai/chat
    integration) - this is what makes the assistant's "I'll report this"
    a real, notified, tracked ticket instead of an empty promise.
  - The officers_for_location superadmin fix in app/utils/scope.py.
  - The new state/district team-chat channel picker in app/routers/messages.py.

Run with:  cd backend && pytest -v
"""
from app.core.security import hash_password
from app.models.member import Member
from app.models.notification import Notification
from app.models.user import User
from app.utils.ai_client import classify_support_message
from app.utils.issue_escalation import create_ai_issue, platform_admins
from app.utils.scope import can_access_channel, officers_for_location

from tests.conftest import get_auth_header


# --- classify_support_message local fallback ---------------------------------

def test_classify_support_message_detects_clear_portal_bug_without_api_key():
    """A clear technical failure must reach the real issue workflow even
    when the optional AI provider is not configured."""
    result = classify_support_message(
        "I uploaded my document but the status did not update until I refreshed the page.",
        history=[],
    )
    assert result["is_issue"] is True
    assert result["category"] == "portal"
    assert result["title"] == "Upload status does not refresh"


def test_classify_support_message_keeps_ordinary_questions_out_of_the_issue_queue():
    result = classify_support_message("What documents do I need for this scheme?", history=[])
    assert result == {"is_issue": False, "category": None, "title": None, "description": None}


# --- create_ai_issue notification routing -------------------------------------

def _make_officers(db_session):
    superadmin = User(full_name="Super Admin", email="super@test.local", hashed_password=hash_password("x"), role="admin", jurisdiction_level="super")
    state_admin = User(full_name="State Admin", email="state@test.local", hashed_password=hash_password("x"), role="admin")
    guntur_admin = User(full_name="Guntur Admin", email="gunturadmin@test.local", hashed_password=hash_password("x"), role="admin", jurisdiction_level="district", district="Guntur")
    guntur_mandal_staff = User(full_name="Guntur Mandal Staff", email="gunturstaff@test.local", hashed_password=hash_password("x"), role="staff", jurisdiction_level="mandal", district="Guntur", mandal="Guntur Urban")
    kakinada_admin = User(full_name="Kakinada Admin", email="kakinadaadmin@test.local", hashed_password=hash_password("x"), role="admin", jurisdiction_level="district", district="Kakinada")
    db_session.add_all([superadmin, state_admin, guntur_admin, guntur_mandal_staff, kakinada_admin])
    db_session.commit()
    return superadmin, state_admin, guntur_admin, guntur_mandal_staff, kakinada_admin


def test_create_ai_issue_portal_category_notifies_only_state_and_super_admins(db_session):
    superadmin, state_admin, guntur_admin, guntur_mandal_staff, kakinada_admin = _make_officers(db_session)
    citizen = User(full_name="Reporter Citizen", email="reporter@test.local", hashed_password=hash_password("x"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)

    issue, audience = create_ai_issue(db_session, reporter=citizen, category="portal", title="Status doesn't update", description="Had to refresh the page.")
    db_session.commit()
    db_session.refresh(issue)

    assert issue.category == "portal"
    assert issue.source == "ai_assistant"
    assert issue.district is None and issue.mandal is None
    assert audience == "the platform administrators"

    notified_user_ids = {n.user_id for n in db_session.query(Notification).filter(Notification.issue_id == issue.id).all()}
    assert notified_user_ids == {citizen.id, superadmin.id, state_admin.id}
    assert guntur_admin.id not in notified_user_ids
    assert guntur_mandal_staff.id not in notified_user_ids
    assert kakinada_admin.id not in notified_user_ids


def test_create_ai_issue_application_category_notifies_every_staff_and_admin(db_session):
    superadmin, state_admin, guntur_admin, guntur_mandal_staff, kakinada_admin = _make_officers(db_session)
    citizen = User(full_name="Guntur Reporter", email="gunturreporter@test.local", hashed_password=hash_password("x"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)
    member = Member(user_id=citizen.id, full_name="Guntur Reporter", address="Addr", village="V", district="Guntur", mandal="Guntur Urban")
    db_session.add(member)
    db_session.commit()

    issue, audience = create_ai_issue(db_session, reporter=citizen, category="application", title="Application stuck", description="Pending for weeks.")
    db_session.commit()
    db_session.refresh(issue)

    assert issue.category == "application"
    assert issue.district == "Guntur" and issue.mandal == "Guntur Urban"
    assert audience == "all staff and administrators"

    notified_user_ids = {n.user_id for n in db_session.query(Notification).filter(Notification.issue_id == issue.id).all()}
    assert guntur_admin.id in notified_user_ids
    assert guntur_mandal_staff.id in notified_user_ids
    assert superadmin.id in notified_user_ids  # state/super admins always have oversight
    assert state_admin.id in notified_user_ids
    assert kakinada_admin.id in notified_user_ids  # service issues are visible to the complete team
    assert citizen.id in notified_user_ids  # report acknowledgement drives the citizen AI badge


def test_platform_admins_excludes_district_admins():
    admins = [
        User(id=1, role="admin", jurisdiction_level="super", full_name="a", email="a", hashed_password="x", is_active=True),
        User(id=2, role="admin", jurisdiction_level=None, full_name="b", email="b", hashed_password="x", is_active=True),
        User(id=3, role="admin", jurisdiction_level="district", district="Guntur", full_name="c", email="c", hashed_password="x", is_active=True),
    ]

    class _FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return admins

    class _FakeDB:
        def query(self, *a, **k):
            return _FakeQuery()

    result = platform_admins(_FakeDB())
    assert {u.id for u in result} == {1, 2}


# --- officers_for_location superadmin fix -------------------------------------

def test_officers_for_location_includes_superadmin_for_any_district(db_session):
    """Regression test: a superadmin (jurisdiction_level='super', no
    district) must be returned for a request from ANY district - the raw
    SQL predicate previously omitted 'super' from its jurisdiction_level
    check, so a superadmin silently never received these notifications."""
    superadmin = User(full_name="Super Admin", email="super2@test.local", hashed_password=hash_password("x"), role="admin", jurisdiction_level="super")
    db_session.add(superadmin)
    db_session.commit()

    officers = officers_for_location(db_session.query(User), "Any District At All", "Any Mandal").all()
    assert superadmin.id in {o.id for o in officers}


# --- can_access_channel permission matrix -------------------------------------

def _user(role, jurisdiction_level=None, district=None, mandal=None, id=1):
    return User(id=id, full_name="Test", email=f"u{id}@test.local", hashed_password="x", role=role, jurisdiction_level=jurisdiction_level, district=district, mandal=mandal)


def test_state_admin_can_access_every_channel():
    state_admin = _user("admin")
    assert can_access_channel(state_admin, None, None)
    assert can_access_channel(state_admin, "Krishna", None)
    assert can_access_channel(state_admin, "Krishna", "Machilipatnam")


def test_district_admin_can_access_own_district_and_its_mandals_only():
    district_admin = _user("admin", jurisdiction_level="district", district="Krishna")
    assert can_access_channel(district_admin, "Krishna", None)
    assert can_access_channel(district_admin, "Krishna", "Machilipatnam")
    assert not can_access_channel(district_admin, "Guntur", None)
    assert not can_access_channel(district_admin, None, None)  # not the all-staff channel


def test_mandal_staff_can_access_only_their_own_mandal():
    mandal_staff = _user("staff", jurisdiction_level="mandal", district="Krishna", mandal="Machilipatnam")
    assert can_access_channel(mandal_staff, "Krishna", "Machilipatnam")
    assert not can_access_channel(mandal_staff, "Krishna", "Gudivada")
    assert not can_access_channel(mandal_staff, None, None)


# --- /api/ai/chat escalation end-to-end ---------------------------------------

def test_ai_chat_escalates_portal_bug_and_notifies_admin(client, seeded_admin, db_session, monkeypatch):
    citizen = User(full_name="Bug Reporter", email="bugreporter@test.local", hashed_password=hash_password("BugPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    import app.routers.ai_assistant as ai_assistant_module
    monkeypatch.setattr(ai_assistant_module, "classify_support_message", lambda message, history=None: {
        "is_issue": True, "category": "portal", "title": "Status not updating", "description": "Had to refresh to see the change.",
    })
    monkeypatch.setattr(ai_assistant_module, "ask_ai", lambda system_prompt, message, history=None: "Logged as a ticket, thanks!")
    monkeypatch.setattr(ai_assistant_module, "ask_ai_with_tools",
                        lambda system_prompt, message, history, tools, execute: ("Logged as a ticket, thanks!", []))

    headers = get_auth_header(client, "bugreporter@test.local", "BugPass123")
    res = client.post("/api/ai/chat", json={"message": "the status doesn't update", "history": []}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["reply"] == "Logged as a ticket, thanks!"

    from app.models.issue import Issue
    issue = db_session.query(Issue).filter(Issue.source == "ai_assistant").first()
    assert issue is not None
    assert issue.category == "portal"
    assert issue.citizen_user_id == citizen.id

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    nav = client.get("/api/dashboard/nav-counts", headers=admin_headers).json()
    assert nav["assistant"] >= 1
    assert nav["issues"] >= 1


def test_ai_chat_logs_the_real_upload_refresh_bug_without_ai_provider(client, seeded_admin, db_session, monkeypatch):
    """Regression for the reported upload flow: the local detector must
    create a portal ticket rather than let an unconfigured assistant make an
    empty promise to report it."""
    citizen = User(full_name="Upload Reporter", email="uploadreporter@test.local", hashed_password=hash_password("UploadPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    import app.routers.ai_assistant as ai_assistant_module
    monkeypatch.setattr(ai_assistant_module, "ask_ai", lambda system_prompt, message, history=None: "Ticket recorded.")
    monkeypatch.setattr(ai_assistant_module, "ask_ai_with_tools",
                        lambda system_prompt, message, history, tools, execute: ("Ticket recorded.", []))

    headers = get_auth_header(client, "uploadreporter@test.local", "UploadPass123")
    res = client.post(
        "/api/ai/chat",
        json={"message": "I uploaded the document, but it did not update until I refreshed the page.", "history": []},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    from app.models.issue import Issue
    issue = db_session.query(Issue).filter(Issue.citizen_user_id == citizen.id, Issue.source == "ai_assistant").one()
    assert issue.category == "portal"
    assert "refresh" in issue.description.lower()


def test_ai_chat_ordinary_question_does_not_create_an_issue(client, seeded_admin, db_session, monkeypatch):
    citizen = User(full_name="Curious Citizen", email="curious@test.local", hashed_password=hash_password("CuriousPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    import app.routers.ai_assistant as ai_assistant_module
    monkeypatch.setattr(ai_assistant_module, "classify_support_message", lambda message, history=None: {
        "is_issue": False, "category": None, "title": None, "description": None,
    })
    monkeypatch.setattr(ai_assistant_module, "ask_ai", lambda system_prompt, message, history=None: "Here is how eligibility works...")
    monkeypatch.setattr(ai_assistant_module, "ask_ai_with_tools",
                        lambda system_prompt, message, history, tools, execute: ("Here is how eligibility works...", []))

    headers = get_auth_header(client, "curious@test.local", "CuriousPass123")
    res = client.post("/api/ai/chat", json={"message": "what documents do I need?", "history": []}, headers=headers)
    assert res.status_code == 200

    from app.models.issue import Issue
    assert db_session.query(Issue).filter(Issue.source == "ai_assistant").count() == 0


# --- team chat channel picker end-to-end --------------------------------------

def test_district_admin_channel_access_scoped_to_own_district(client, db_session):
    guntur_admin = User(full_name="Guntur Admin", email="gunturadmin2@test.local", hashed_password=hash_password("GunturPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    db_session.add(guntur_admin)
    db_session.commit()
    headers = get_auth_header(client, "gunturadmin2@test.local", "GunturPass123")

    ok = client.get("/api/messages/internal", params={"scope": "district", "district": "Guntur"}, headers=headers)
    assert ok.status_code == 200

    forbidden = client.get("/api/messages/internal", params={"scope": "district", "district": "Kakinada"}, headers=headers)
    assert forbidden.status_code == 403

    forbidden_all = client.get("/api/messages/internal", params={"scope": "all"}, headers=headers)
    assert forbidden_all.status_code == 403


def test_posting_to_mandal_channel_notifies_mandal_staff_and_district_admin_not_other_district(client, db_session):
    guntur_admin = User(full_name="Guntur Admin", email="gunturadmin3@test.local", hashed_password=hash_password("GunturPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    mandal_staff = User(full_name="Guntur Urban Staff", email="gustaff@test.local", hashed_password=hash_password("StaffPass123"), role="staff", jurisdiction_level="mandal", district="Guntur", mandal="Guntur Urban")
    other_mandal_staff = User(full_name="Tenali Staff", email="tenalistaff@test.local", hashed_password=hash_password("StaffPass123"), role="staff", jurisdiction_level="mandal", district="Guntur", mandal="Tenali")
    db_session.add_all([guntur_admin, mandal_staff, other_mandal_staff])
    db_session.commit()

    headers = get_auth_header(client, "gunturadmin3@test.local", "GunturPass123")
    res = client.post(
        "/api/messages/internal",
        json={"body": "Please check the ration card backlog", "scope": "mandal", "district": "Guntur", "mandal": "Guntur Urban"},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    staff_headers = get_auth_header(client, "gustaff@test.local", "StaffPass123")
    counts = client.get("/api/messages/internal/unread-counts", headers=staff_headers).json()
    assert counts.get("/chat?scope=mandal&district=Guntur&mandal=Guntur%20Urban", 0) == 1

    other_staff_headers = get_auth_header(client, "tenalistaff@test.local", "StaffPass123")
    other_counts = client.get("/api/messages/internal/unread-counts", headers=other_staff_headers).json()
    assert other_counts == {}

    # Reading the channel marks it read.
    thread = client.get("/api/messages/internal", params={"scope": "mandal", "district": "Guntur", "mandal": "Guntur Urban"}, headers=staff_headers)
    assert thread.status_code == 200
    assert len(thread.json()) == 1
    cleared = client.get("/api/messages/internal/unread-counts", headers=staff_headers).json()
    assert cleared == {}


def test_statewide_team_chat_notifies_every_active_officer(client, db_session):
    """The All Staff & Admins channel is a genuine statewide room, not a
    state-admin-only notification target. District and mandal officers must
    receive its badge and its notification link."""
    state_admin = User(full_name="State Admin Broadcast", email="statebroadcast@test.local", hashed_password=hash_password("StatePass123"), role="admin")
    guntur_admin = User(full_name="Guntur Broadcast Admin", email="gunturbroadcast@test.local", hashed_password=hash_password("GunturPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    kakinada_staff = User(full_name="Kakinada Broadcast Staff", email="kakinadabroadcast@test.local", hashed_password=hash_password("StaffPass123"), role="staff", jurisdiction_level="mandal", district="Kakinada", mandal="Kakinada Rural")
    db_session.add_all([state_admin, guntur_admin, kakinada_staff])
    db_session.commit()

    state_headers = get_auth_header(client, "statebroadcast@test.local", "StatePass123")
    res = client.post(
        "/api/messages/internal",
        json={"body": "Statewide service update", "scope": "all"},
        headers=state_headers,
    )
    assert res.status_code == 201, res.text

    for email, password in (("gunturbroadcast@test.local", "GunturPass123"), ("kakinadabroadcast@test.local", "StaffPass123")):
        headers = get_auth_header(client, email, password)
        counts = client.get("/api/messages/internal/unread-counts", headers=headers).json()
        assert counts.get("/chat?scope=all", 0) == 1


def test_mandal_staff_cannot_post_to_a_different_mandal(client, db_session):
    mandal_staff = User(full_name="Guntur Urban Staff Two", email="gustaff2@test.local", hashed_password=hash_password("StaffPass123"), role="staff", jurisdiction_level="mandal", district="Guntur", mandal="Guntur Urban")
    db_session.add(mandal_staff)
    db_session.commit()
    headers = get_auth_header(client, "gustaff2@test.local", "StaffPass123")

    res = client.post(
        "/api/messages/internal",
        json={"body": "hello", "scope": "mandal", "district": "Guntur", "mandal": "Tenali"},
        headers=headers,
    )
    assert res.status_code == 403


def test_chat_unread_count_combines_citizen_and_team_totals(client, db_session):
    guntur_admin = User(full_name="Guntur Admin Four", email="gunturadmin4@test.local", hashed_password=hash_password("GunturPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    db_session.add(guntur_admin)
    db_session.commit()
    headers = get_auth_header(client, "gunturadmin4@test.local", "GunturPass123")

    before = client.get("/api/messages/unread-count", headers=headers).json()
    assert before == {"unread_count": 0, "citizen_unread": 0, "team_unread": 0}

    client.post("/api/messages/internal", json={"body": "district note", "scope": "district", "district": "Guntur"}, headers=headers)
    # The sender itself isn't notified of its own message.
    after_own_post = client.get("/api/messages/unread-count", headers=headers).json()
    assert after_own_post["team_unread"] == 0

    second_admin = User(full_name="Guntur Admin Five", email="gunturadmin5@test.local", hashed_password=hash_password("GunturPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    db_session.add(second_admin)
    db_session.commit()
    second_headers = get_auth_header(client, "gunturadmin5@test.local", "GunturPass123")
    client.post("/api/messages/internal", json={"body": "another note", "scope": "district", "district": "Guntur"}, headers=second_headers)

    after = client.get("/api/messages/unread-count", headers=headers).json()
    assert after["team_unread"] == 1
    assert after["unread_count"] == after["citizen_unread"] + after["team_unread"]
