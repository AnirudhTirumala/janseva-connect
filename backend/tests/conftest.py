"""
Shared pytest fixtures. Tests run against an isolated in-memory SQLite
database (never the real panchayat.db), created fresh for every test
function, so tests can't corrupt real data and don't depend on
execution order.
"""
import os

# Force safe test-only settings before any app module is imported, so
# nothing accidentally touches real credentials or a real database file.
os.environ["SECRET_KEY"] = "test-only-secret-not-for-production-use-1234567890"
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["GROQ_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["TESTING"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User
from app.models.scheme import Scheme, SchemeDocumentRequirement


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_admin(db_session):
    admin = User(
        full_name="Test Admin", email="admin@test.local",
        hashed_password=hash_password("AdminPass123"), role="admin",
    )
    staff = User(
        full_name="Test Staff", email="staff@test.local",
        hashed_password=hash_password("StaffPass123"), role="staff",
    )
    db_session.add_all([admin, staff])
    db_session.commit()
    return admin


@pytest.fixture()
def seeded_superadmin(db_session):
    superadmin = User(
        full_name="Test Superadmin", email="superadmin@test.local",
        hashed_password=hash_password("SuperPass123"), role="admin", jurisdiction_level="super",
    )
    db_session.add(superadmin)
    db_session.commit()
    return superadmin


@pytest.fixture()
def seeded_scheme(db_session):
    scheme = Scheme(name="Test Scheme", description="A scheme for testing.", max_income_limit=100000)
    db_session.add(scheme)
    db_session.flush()
    db_session.add(SchemeDocumentRequirement(scheme_id=scheme.id, name="Aadhaar Card"))
    db_session.commit()
    return scheme


def get_auth_header(client, email, password):
    res = client.post("/api/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
