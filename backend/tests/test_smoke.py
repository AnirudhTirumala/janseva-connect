"""
Smoke tests for the core flows that matter most: auth/security boundaries,
the member -> scheme -> application -> certificate lifecycle, and the
rules that were added specifically for transparency/security (remarks
required on rejection, role checks, rate limiting headers present, etc).

Run with:  cd backend && pytest -v
"""
from tests.conftest import get_auth_header


# --- Health & basic wiring ---------------------------------------------------

def test_health_check(client):
    """Health must confirm the database too - a constant "ok" would keep
    reporting healthy while every real request fails on a dead connection."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok"}


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"


# --- Auth & role boundaries ---------------------------------------------------

def test_login_wrong_password_rejected(client, seeded_admin):
    res = client.post("/api/auth/login", data={"username": "admin@test.local", "password": "wrong"})
    assert res.status_code == 401


def test_login_correct_password_returns_token(client, seeded_admin):
    res = client.post("/api/auth/login", data={"username": "admin@test.local", "password": "AdminPass123"})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["role"] == "admin"


def test_unauthenticated_request_rejected(client):
    res = client.get("/api/members/")
    assert res.status_code == 401


def test_staff_cannot_access_admin_only_route(client, seeded_admin):
    headers = get_auth_header(client, "staff@test.local", "StaffPass123")
    res = client.get("/api/users/", headers=headers)
    assert res.status_code == 403


def test_admin_can_access_admin_only_route(client, seeded_admin):
    headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.get("/api/users/", headers=headers)
    assert res.status_code == 200


def test_citizen_cannot_create_member_directly(client, seeded_admin, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="Citizen One", email="citizen1@test.local", hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    headers = get_auth_header(client, "citizen1@test.local", "CitizenPass123")
    res = client.post("/api/members/", json={"full_name": "X", "address": "Y", "village": "Z"}, headers=headers)
    assert res.status_code == 403


# --- Member -> Scheme -> Application -> Certificate lifecycle ----------------

def test_member_creation_sanitizes_blank_optional_fields(client, seeded_admin):
    headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.post(
        "/api/members/",
        json={"full_name": "Blank Fields Test", "address": "Addr", "village": "Village", "aadhaar_number": ""},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["aadhaar_number"] is None


def test_full_application_lifecycle(client, seeded_admin, seeded_scheme, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="Lifecycle Citizen", email="lifecycle@test.local", hashed_password=hash_password("LifePass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers = get_auth_header(client, "lifecycle@test.local", "LifePass123")

    res = client.post(
        "/api/members/me",
        json={"full_name": "Lifecycle Citizen", "address": "Addr", "village": "Village"},
        headers=citizen_headers,
    )
    assert res.status_code == 201, res.text

    res = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    application_id = res.json()["id"]
    assert res.json()["status"] == "pending"
    requirement_id = seeded_scheme.document_requirements[0].id

    res = client.patch(
        f"/api/applications/{application_id}/review",
        json={"status": "rejected"},
        headers=admin_headers,
    )
    assert res.status_code == 422

    res = client.patch(
        f"/api/applications/{application_id}/review",
        json={"status": "rejected", "remarks": "Missing documents"},
        headers=admin_headers,
    )
    assert res.status_code == 409

    # A scheme-level decision is blocked until the required document has
    # been uploaded *and* individually reviewed by the office.
    res = client.post(
        f"/api/applications/{application_id}/documents",
        data={"document_name": "Aadhaar Card", "requirement_id": str(requirement_id)},
        files={"file": ("aadhaar.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=citizen_headers,
    )
    assert res.status_code == 201, res.text
    document_id = res.json()["id"]

    res = client.patch(
        f"/api/applications/{application_id}/review",
        json={"status": "rejected", "remarks": "Missing documents"},
        headers=admin_headers,
    )
    assert res.status_code == 409

    res = client.patch(
        f"/api/applications/{application_id}/documents/{document_id}/review",
        json={"status": "approved"},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text

    res = client.patch(
        f"/api/applications/{application_id}/review",
        json={"status": "rejected", "remarks": "Missing documents"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"
    assert res.json()["reviewed_by_name"] == "Test Admin"

    res = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    new_application_id = res.json()["id"]
    assert new_application_id != application_id

    res = client.post(
        f"/api/applications/{new_application_id}/documents",
        data={"document_name": "Aadhaar Card", "requirement_id": str(requirement_id)},
        files={"file": ("aadhaar-again.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=citizen_headers,
    )
    assert res.status_code == 201, res.text
    second_document_id = res.json()["id"]

    res = client.patch(
        f"/api/applications/{new_application_id}/documents/{second_document_id}/review",
        json={"status": "approved"},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text

    res = client.patch(
        f"/api/applications/{new_application_id}/review",
        json={"status": "approved", "remarks": "All good"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    res = client.get(f"/api/applications/{new_application_id}/approval-pdf/download", headers=citizen_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"


def test_application_not_documents_complete_until_mandatory_upload_exists(client, seeded_admin, seeded_scheme, db_session):
    """Regression test: applying used to immediately look identical to a
    fully-complete application from the frontend's point of view, even
    with zero documents uploaded, because there was no way to tell the
    two apart. documents_complete must be False right after applying
    (the scheme has one mandatory document) and True only once it's
    actually uploaded."""
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="Docs Citizen", email="docscitizen@test.local", hashed_password=hash_password("DocsPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    citizen_headers = get_auth_header(client, "docscitizen@test.local", "DocsPass123")
    res = client.post("/api/members/me", json={"full_name": "Docs Citizen", "address": "Addr", "village": "Village"}, headers=citizen_headers)
    assert res.status_code == 201, res.text

    res = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    application = res.json()
    assert application["documents_complete"] is False
    assert application["required_document_count"] == 1
    assert application["uploaded_document_count"] == 0
    assert application["documents_reviewed"] is False

    requirement_id = seeded_scheme.document_requirements[0].id
    res = client.post(
        f"/api/applications/{application['id']}/documents",
        data={"document_name": "Aadhaar Card", "requirement_id": str(requirement_id)},
        files={"file": ("aadhaar.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=citizen_headers,
    )
    assert res.status_code == 201, res.text

    res = client.get("/api/applications/my", headers=citizen_headers)
    assert res.status_code == 200
    refreshed = res.json()[0]
    assert refreshed["documents_complete"] is True
    assert refreshed["uploaded_document_count"] == 1
    assert refreshed["documents_reviewed"] is False
    assert refreshed["document_review_pending_count"] == 1


def test_mark_read_by_link_only_clears_matching_notifications(client, db_session):
    from app.models.user import User
    from app.models.notification import Notification
    from app.core.security import hash_password
    citizen = User(full_name="Notif Citizen", email="notifcitizen@test.local", hashed_password=hash_password("NotifPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)

    db_session.add_all([
        Notification(user_id=citizen.id, title="App update", link="/applications"),
        Notification(user_id=citizen.id, title="Cert update", link="/certificates"),
    ])
    db_session.commit()

    citizen_headers = get_auth_header(client, "notifcitizen@test.local", "NotifPass123")
    res = client.patch("/api/notifications/read-by-link", params={"link": "/applications"}, headers=citizen_headers)
    assert res.status_code == 200

    res = client.get("/api/dashboard/nav-counts", headers=citizen_headers)
    counts = res.json()
    assert counts["applications"] == 0
    assert counts["certificates"] == 1


def test_district_staff_cannot_access_another_districts_application_documents(client, seeded_scheme, db_session):
    """Regression test for the security fix: a staff account scoped to one
    district must not be able to list/download/review the uploaded
    documents (Aadhaar cards etc.) of an application belonging to a citizen
    in a different district, even though application/document IDs are
    small sequential integers that are trivial to guess."""
    from app.models.user import User
    from app.models.member import Member
    from app.core.security import hash_password

    citizen = User(full_name="Guntur Citizen", email="gunturcitizen@test.local", hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)
    member = Member(user_id=citizen.id, full_name="Guntur Citizen", address="Addr", village="Village", district="Guntur")
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)

    other_district_staff = User(full_name="Kakinada Staff", email="kakinadastaff@test.local", hashed_password=hash_password("StaffPass123"), role="staff", jurisdiction_level="district", district="Kakinada")
    db_session.add(other_district_staff)
    db_session.commit()

    citizen_headers = get_auth_header(client, "gunturcitizen@test.local", "CitizenPass123")
    res = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    application_id = res.json()["id"]

    res = client.post(
        f"/api/applications/{application_id}/documents",
        data={"document_name": "Aadhaar Card"},
        files={"file": ("aadhaar.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=citizen_headers,
    )
    assert res.status_code == 201, res.text
    document_id = res.json()["id"]

    other_staff_headers = get_auth_header(client, "kakinadastaff@test.local", "StaffPass123")
    assert client.get(f"/api/applications/{application_id}/documents", headers=other_staff_headers).status_code == 403
    assert client.get(f"/api/applications/{application_id}/documents/{document_id}/download", headers=other_staff_headers).status_code == 403
    assert client.patch(f"/api/applications/{application_id}/documents/{document_id}/review", json={"status": "approved"}, headers=other_staff_headers).status_code == 403


def test_certificate_issuance_and_download(client, seeded_admin):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.post(
        "/api/members/", json={"full_name": "Cert Test", "address": "Addr", "village": "Village"}, headers=admin_headers,
    )
    member_id = res.json()["id"]

    res = client.post(
        "/api/certificates/", json={"member_id": member_id, "certificate_type": "income"}, headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    cert_id = res.json()["id"]
    assert res.json()["certificate_number"].startswith("INC-")

    res = client.get(f"/api/certificates/{cert_id}/download", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"


def test_citizen_certificate_request_review_issue_and_download(client, seeded_admin, db_session):
    from app.models.user import User
    from app.core.security import hash_password

    citizen = User(full_name="Request Citizen", email="request@test.local", hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers = get_auth_header(client, "request@test.local", "CitizenPass123")

    res = client.post("/api/members/me", json={"full_name": "Request Citizen", "address": "Addr", "village": "Village"}, headers=citizen_headers)
    assert res.status_code == 201, res.text

    res = client.post("/api/certificates/requests", json={"certificate_type": "income", "purpose": "Bank application"}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    request_id = res.json()["id"]

    assert client.get("/api/certificates/requests", headers=citizen_headers).json()[0]["id"] == request_id
    assert client.get("/api/certificates/requests", headers=admin_headers).json()[0]["requested_by_name"] == "Request Citizen"
    assert client.patch(f"/api/certificates/requests/{request_id}", json={"status": "rejected"}, headers=admin_headers).status_code == 422

    res = client.patch(f"/api/certificates/requests/{request_id}", json={"status": "approved"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"

    res = client.post(f"/api/certificates/requests/{request_id}/issue", headers=admin_headers)
    assert res.status_code == 201, res.text
    certificate_id = res.json()["id"]
    assert client.get(f"/api/certificates/{certificate_id}/download", headers=citizen_headers).status_code == 200


def test_document_rejection_requires_remarks(client, seeded_admin, seeded_scheme, db_session, tmp_path):
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="Doc Citizen", email="doccitizen@test.local", hashed_password=hash_password("DocPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers = get_auth_header(client, "doccitizen@test.local", "DocPass123")

    client.post("/api/members/me", json={"full_name": "Doc Citizen", "address": "Addr", "village": "Village"}, headers=citizen_headers)
    res = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers)
    application_id = res.json()["id"]

    requirement_id = seeded_scheme.document_requirements[0].id
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF-1.4 fake content")

    with open(test_file, "rb") as f:
        res = client.post(
            f"/api/applications/{application_id}/documents",
            data={"document_name": "Aadhaar Card", "requirement_id": requirement_id},
            files={"file": ("test.pdf", f, "application/pdf")},
            headers=citizen_headers,
        )
    assert res.status_code == 201, res.text
    document_id = res.json()["id"]

    res = client.patch(
        f"/api/applications/{application_id}/documents/{document_id}/review",
        json={"status": "rejected"},
        headers=admin_headers,
    )
    assert res.status_code == 422


# --- Chat transparency ---------------------------------------------------

def test_all_staff_see_same_conversation(client, seeded_admin, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="Chat Citizen", email="chatcitizen@test.local", hashed_password=hash_password("ChatPass123"), role="citizen")
    staff2 = User(full_name="Second Staff", email="staff2@test.local", hashed_password=hash_password("Staff2Pass123"), role="staff")
    db_session.add_all([citizen, staff2])
    db_session.commit()

    citizen_headers = get_auth_header(client, "chatcitizen@test.local", "ChatPass123")
    staff1_headers = get_auth_header(client, "staff@test.local", "StaffPass123")
    staff2_headers = get_auth_header(client, "staff2@test.local", "Staff2Pass123")

    client.post("/api/messages/", json={"body": "Hello from citizen"}, headers=citizen_headers)
    client.post(
        "/api/messages/", json={"body": "Reply from staff one", "citizen_user_id": citizen.id}, headers=staff1_headers,
    )

    res = client.get(f"/api/messages/thread/{citizen.id}", headers=staff2_headers)
    assert res.status_code == 200
    bodies = [m["body"] for m in res.json()]
    assert "Hello from citizen" in bodies
    assert "Reply from staff one" in bodies


def test_conversations_list_includes_citizens_without_messages(client, seeded_admin, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    citizen = User(full_name="No Message Citizen", email="nomsg@test.local", hashed_password=hash_password("NoMsgPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.get("/api/messages/conversations", headers=admin_headers)
    assert res.status_code == 200
    names = [c["citizen_name"] for c in res.json()]
    assert "No Message Citizen" in names


# --- Superadmin tier -----------------------------------------------------

def test_superadmin_can_appoint_a_state_admin(client, seeded_superadmin, monkeypatch):
    delivered_codes = []
    monkeypatch.setattr(
        "app.routers.users.send_otp_email",
        lambda _email, code, _purpose: delivered_codes.append(code) or True,
    )
    superadmin_headers = get_auth_header(client, "superadmin@test.local", "SuperPass123")

    res = client.post(
        "/api/users/request",
        json={
            "full_name": "New State Admin", "email": "newstateadmin@example.com", "password": "StateAdminPass123",
            "role": "admin", "jurisdiction_level": "state",
        },
        headers=superadmin_headers,
    )
    assert res.status_code == 202, res.text

    assert len(delivered_codes) == 1
    res = client.post("/api/users/confirm", json={"email": "newstateadmin@example.com", "code": delivered_codes[0]}, headers=superadmin_headers)
    assert res.status_code == 201, res.text
    assert res.json()["jurisdiction_level"] == "state"
    assert res.json()["district"] is None


def test_plain_state_admin_cannot_appoint_a_state_admin(client, seeded_admin):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.post(
        "/api/users/request",
        json={
            "full_name": "Should Fail", "email": "shouldfail@example.com", "password": "ShouldFailPass123",
            "role": "admin", "jurisdiction_level": "state",
        },
        headers=admin_headers,
    )
    assert res.status_code == 403


def test_superadmin_account_cannot_be_deactivated(client, seeded_superadmin, seeded_admin):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.patch(f"/api/users/{seeded_superadmin.id}/deactivate", headers=admin_headers)
    assert res.status_code == 400


def test_superadmin_can_post_team_chat_without_a_district(client, seeded_superadmin):
    superadmin_headers = get_auth_header(client, "superadmin@test.local", "SuperPass123")
    res = client.post("/api/messages/internal", json={"body": "State-wide reminder"}, headers=superadmin_headers)
    assert res.status_code == 201, res.text
    assert res.json()["district"] == "STATEWIDE"


def test_staff_without_a_district_is_blocked_from_team_chat(client, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    staff = User(full_name="No District Staff", email="nodistrict@test.local", hashed_password=hash_password("NoDistrictPass123"), role="staff")
    db_session.add(staff)
    db_session.commit()

    headers = get_auth_header(client, "nodistrict@test.local", "NoDistrictPass123")
    res = client.post("/api/messages/internal", json={"body": "Hello team"}, headers=headers)
    assert res.status_code == 422


# --- Certificate deletion ---------------------------------------------------

def test_only_superadmin_can_delete_an_issued_certificate(client, seeded_admin, seeded_superadmin):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.post("/api/members/", json={"full_name": "Delete Cert Test", "address": "Addr", "village": "Village"}, headers=admin_headers)
    member_id = res.json()["id"]
    res = client.post("/api/certificates/", json={"member_id": member_id, "certificate_type": "income"}, headers=admin_headers)
    cert_id = res.json()["id"]

    res = client.delete(f"/api/certificates/{cert_id}", headers=admin_headers)
    assert res.status_code == 403, res.text

    superadmin_headers = get_auth_header(client, "superadmin@test.local", "SuperPass123")
    res = client.delete(f"/api/certificates/{cert_id}", headers=superadmin_headers)
    assert res.status_code == 204, res.text

    res = client.get(f"/api/certificates/{cert_id}/download", headers=admin_headers)
    assert res.status_code == 404


def test_state_admin_retires_scheme_with_application_instead_of_breaking_history(client, seeded_admin, seeded_scheme, db_session):
    """Regression for the SQLite NOT NULL error from DELETE /api/schemes/{id}."""
    from app.models.member import Member
    from app.models.application import SchemeApplication
    from app.models.user import User
    from app.core.security import hash_password

    citizen = User(full_name="Scheme History Citizen", email="schemehistory@test.local", hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.flush()
    member = Member(user_id=citizen.id, full_name=citizen.full_name, address="Addr", village="Village", district="Guntur", mandal="Guntur Urban")
    db_session.add(member)
    db_session.flush()
    db_session.add(SchemeApplication(member_id=member.id, scheme_id=seeded_scheme.id, status="pending"))
    db_session.commit()

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    res = client.delete(f"/api/schemes/{seeded_scheme.id}", headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["action"] == "retired"

    app = db_session.query(SchemeApplication).filter(SchemeApplication.scheme_id == seeded_scheme.id).first()
    assert app is not None


# --- Issue accept/reject workflow -------------------------------------------

def _citizen_with_issue(db_session, client, admin_headers, email="issuecitizen@test.local"):
    from app.models.user import User
    from app.models.member import Member
    from app.core.security import hash_password
    citizen = User(full_name="Issue Citizen", email=email, hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)
    member = Member(user_id=citizen.id, full_name="Issue Citizen", address="Addr", village="Village", district="Guntur", mandal="Guntur Urban")
    db_session.add(member)
    db_session.commit()

    citizen_headers = get_auth_header(client, email, "CitizenPass123")
    res = client.post("/api/issues/", json={"title": "Broken streetlight", "description": "The streetlight near the bus stand is broken."}, headers=citizen_headers)
    assert res.status_code == 201, res.text
    return citizen_headers, res.json()["id"]


def test_citizen_accepting_a_resolved_issue_closes_it(client, seeded_admin, db_session):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers, issue_id = _citizen_with_issue(db_session, client, admin_headers)

    res = client.patch(f"/api/issues/{issue_id}", json={"status": "resolved", "reply": "Fixed the streetlight."}, headers=admin_headers)
    assert res.status_code == 200, res.text

    res = client.patch(f"/api/issues/{issue_id}/respond", json={"accepted": True}, headers=citizen_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "closed"


def test_citizen_rejecting_a_resolved_issue_reopens_it_with_feedback(client, seeded_admin, db_session):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers, issue_id = _citizen_with_issue(db_session, client, admin_headers, email="issuecitizen2@test.local")

    client.patch(f"/api/issues/{issue_id}", json={"status": "resolved", "reply": "Fixed the streetlight."}, headers=admin_headers)

    res = client.patch(f"/api/issues/{issue_id}/respond", json={"accepted": False, "feedback": "Still broken at night."}, headers=citizen_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "reopened"
    assert res.json()["citizen_feedback"] == "Still broken at night."


def test_cannot_respond_to_an_issue_that_is_not_resolved(client, seeded_admin, db_session):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    citizen_headers, issue_id = _citizen_with_issue(db_session, client, admin_headers, email="issuecitizen3@test.local")

    res = client.patch(f"/api/issues/{issue_id}/respond", json={"accepted": True}, headers=citizen_headers)
    assert res.status_code == 400


def test_citizen_cannot_respond_to_someone_elses_issue(client, seeded_admin, db_session):
    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    _, issue_id = _citizen_with_issue(db_session, client, admin_headers, email="issuecitizen4@test.local")
    client.patch(f"/api/issues/{issue_id}", json={"status": "resolved", "reply": "Fixed."}, headers=admin_headers)

    from app.models.user import User
    from app.core.security import hash_password
    other_citizen = User(full_name="Other Citizen", email="othercitizen@test.local", hashed_password=hash_password("OtherPass123"), role="citizen")
    db_session.add(other_citizen)
    db_session.commit()
    other_headers = get_auth_header(client, "othercitizen@test.local", "OtherPass123")

    res = client.patch(f"/api/issues/{issue_id}/respond", json={"accepted": True}, headers=other_headers)
    assert res.status_code == 403


def test_superadmin_can_delete_a_district_admin(client, seeded_superadmin, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    district_admin = User(full_name="District Admin", email="districtadmin@test.local", hashed_password=hash_password("DistrictPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    db_session.add(district_admin)
    db_session.commit()
    db_session.refresh(district_admin)

    superadmin_headers = get_auth_header(client, "superadmin@test.local", "SuperPass123")
    res = client.delete(f"/api/users/{district_admin.id}", headers=superadmin_headers)
    assert res.status_code == 204, res.text


def test_ai_assistant_sees_citizens_own_certificates_and_applications(db_session):
    """The AI assistant should be able to answer "what certificates were
    issued to me" - this was previously impossible since the assistant only
    ever saw the general catalog, never an individual citizen's own record."""
    from app.models.user import User
    from app.models.member import Member
    from app.models.certificate import Certificate
    from app.models.certificate_type import CertificateType
    from app.models.scheme import Scheme
    from app.models.application import SchemeApplication
    from app.core.security import hash_password
    from app.routers.ai_assistant import _citizen_own_records_context

    citizen = User(full_name="AI Test Citizen", email="aitestcitizen@test.local", hashed_password=hash_password("CitizenPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)

    member = Member(user_id=citizen.id, full_name="AI Test Citizen", address="Addr", village="Village", district="Guntur")
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)

    cert_type = CertificateType(key="income", name="Income Certificate", prefix="INC")
    scheme = Scheme(name="Rural Housing Scheme", description="Housing help", is_active=True)
    db_session.add_all([cert_type, scheme])
    db_session.commit()
    db_session.refresh(scheme)

    certificate = Certificate(member_id=member.id, certificate_type="income", certificate_number="INC-2026-000999", issued_by_id=citizen.id)
    application = SchemeApplication(member_id=member.id, scheme_id=scheme.id, status="approved")
    db_session.add_all([certificate, application])
    db_session.commit()

    context = _citizen_own_records_context(db_session, citizen, [cert_type])
    assert "Income Certificate" in context
    assert "INC-2026-000999" in context
    assert "Rural Housing Scheme" in context
    assert "approved" in context
