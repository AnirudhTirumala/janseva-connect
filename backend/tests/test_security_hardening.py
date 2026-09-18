"""Regression tests for production-facing security controls."""

from tests.conftest import get_auth_header


def test_new_otp_is_hashed_and_a_replaced_code_cannot_be_used(client, monkeypatch, db_session):
    from app.models.otp import EmailOTP

    sent_codes = []
    monkeypatch.setattr(
        "app.routers.auth.send_otp_email",
        lambda _email, code, _purpose: sent_codes.append(code) or True,
    )
    payload = {"full_name": "Hash Test", "email": "hash@example.com", "password": "HashTestPass123"}

    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 200, second.text
    assert len(sent_codes) == 2 and sent_codes[0] != sent_codes[1]

    records = db_session.query(EmailOTP).filter(EmailOTP.email == payload["email"]).order_by(EmailOTP.id).all()
    assert records[-1].code == ""
    assert records[-1].code_hash and sent_codes[-1] not in records[-1].code_hash
    assert records[0].is_used is True

    old = client.post("/api/auth/register/verify", json={"email": payload["email"], "code": sent_codes[0]})
    assert old.status_code == 400
    current = client.post("/api/auth/register/verify", json={"email": payload["email"], "code": sent_codes[1]})
    assert current.status_code == 200


def test_password_reset_revokes_existing_token(client, seeded_admin, db_session, monkeypatch):
    sent_codes = []
    monkeypatch.setattr(
        "app.routers.auth.send_otp_email",
        lambda _email, code, _purpose: sent_codes.append(code) or True,
    )
    seeded_admin.email = "admin@example.com"
    db_session.commit()
    original = get_auth_header(client, "admin@example.com", "AdminPass123")
    assert client.post("/api/auth/password-reset/request", json={"email": "admin@example.com"}).status_code == 200
    assert sent_codes
    reset = client.post(
        "/api/auth/password-reset/confirm",
        json={"email": "admin@example.com", "code": sent_codes[-1], "new_password": "NewAdminPass123"},
    )
    assert reset.status_code == 200
    # The old session must fail immediately; it cannot stay valid until the
    # normal JWT expiry window ends.
    assert client.get("/api/auth/me", headers=original).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {reset.json()['access_token']}"}).status_code == 200


def test_document_upload_rejects_spoofed_content_type(client, seeded_admin, seeded_scheme, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    citizen = User(full_name="Upload Test", email="upload@test.local", hashed_password=hash_password("UploadTestPass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    citizen_headers = get_auth_header(client, "upload@test.local", "UploadTestPass123")
    assert client.post("/api/members/me", json={"full_name": "Upload Test", "address": "Addr", "village": "Village"}, headers=citizen_headers).status_code == 201
    application = client.post("/api/applications/", json={"scheme_id": seeded_scheme.id}, headers=citizen_headers).json()

    response = client.post(
        f"/api/applications/{application['id']}/documents",
        data={"document_name": "Aadhaar Card", "requirement_id": str(seeded_scheme.document_requirements[0].id)},
        files={"file": ("looks-like-a.pdf", b"<script>alert(1)</script>", "application/pdf")},
        headers=citizen_headers,
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_district_admin_cannot_read_global_audit_or_peer_admin(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    district_admin = User(full_name="District Admin", email="districtadmin@test.local", hashed_password=hash_password("DistrictAdminPass123"), role="admin", jurisdiction_level="district", district="Guntur")
    state_admin = User(full_name="State Admin", email="stateadmin@test.local", hashed_password=hash_password("StateAdminPass123"), role="admin", jurisdiction_level="state")
    peer_state_admin = User(full_name="Peer State Admin", email="peerstateadmin@test.local", hashed_password=hash_password("PeerStateAdminPass123"), role="admin", jurisdiction_level="state")
    db_session.add_all([district_admin, state_admin, peer_state_admin])
    db_session.commit()

    district_headers = get_auth_header(client, "districtadmin@test.local", "DistrictAdminPass123")
    assert client.get("/api/audit/events", headers=district_headers).status_code == 403
    assert client.get("/api/audit/otps", headers=district_headers).status_code == 403

    peer_headers = get_auth_header(client, "stateadmin@test.local", "StateAdminPass123")
    assert client.patch(f"/api/users/{peer_state_admin.id}/deactivate", headers=peer_headers).status_code == 403


def test_office_cannot_link_a_citizen_to_multiple_household_profiles(client, seeded_admin, db_session):
    from app.core.security import hash_password
    from app.models.member import Member
    from app.models.user import User

    citizen = User(full_name="One Profile", email="oneprofile@test.local", hashed_password=hash_password("OneProfilePass123"), role="citizen")
    db_session.add(citizen)
    db_session.commit()
    db_session.add(Member(user_id=citizen.id, full_name="One Profile", address="Addr", village="Village"))
    db_session.commit()

    admin_headers = get_auth_header(client, "admin@test.local", "AdminPass123")
    response = client.post(
        "/api/members/",
        json={"full_name": "Duplicate Profile", "address": "Addr", "village": "Village", "user_id": citizen.id},
        headers=admin_headers,
    )
    assert response.status_code == 409
