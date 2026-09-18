"""
Unit tests for the jurisdiction/role scope helpers in app/utils/scope.py,
covering the superadmin tier layered on top of the existing state/district/
mandal hierarchy. These construct User objects directly and call the scope
functions as plain Python - no HTTP layer or database needed - so they're
fast and pin down the exact boundary each function is responsible for.

Run with:  cd backend && pytest -v
"""
from app.models.user import User
from app.utils.scope import (
    is_superadmin, is_state_admin, is_district_admin,
    can_manage_user, can_reassign_officer, can_delete_officer,
)


def _user(role, jurisdiction_level=None, district=None, mandal=None, id=1):
    return User(
        id=id, full_name="Test", email=f"u{id}@test.local", hashed_password="x",
        role=role, jurisdiction_level=jurisdiction_level, district=district, mandal=mandal,
    )


# --- Tier identification --------------------------------------------------

def test_superadmin_is_identified_and_also_counts_as_state_admin():
    superadmin = _user("admin", jurisdiction_level="super")
    assert is_superadmin(superadmin)
    assert is_state_admin(superadmin)  # every existing state-admin-gated check must also grant superadmin access
    assert not is_district_admin(superadmin)


def test_legacy_admin_with_no_jurisdiction_is_state_admin_but_not_superadmin():
    """jurisdiction_level=None predates the state/district/mandal split and is
    treated as a state admin for backward compatibility - it must NOT be
    treated as the superadmin, which requires the explicit 'super' marker."""
    legacy_admin = _user("admin", jurisdiction_level=None)
    assert is_state_admin(legacy_admin)
    assert not is_superadmin(legacy_admin)


def test_district_admin_is_neither_state_admin_nor_superadmin():
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur")
    assert is_district_admin(district_admin)
    assert not is_state_admin(district_admin)
    assert not is_superadmin(district_admin)


def test_staff_is_never_any_kind_of_admin():
    staff = _user("staff", jurisdiction_level="district", district="Guntur")
    assert not is_state_admin(staff)
    assert not is_district_admin(staff)
    assert not is_superadmin(staff)


# --- can_manage_user: who may create whom ---------------------------------

def test_superadmin_can_create_a_state_admin():
    superadmin = _user("admin", jurisdiction_level="super")
    assert can_manage_user(superadmin, "admin", None, "state") is True


def test_superadmin_can_create_a_district_admin_too():
    superadmin = _user("admin", jurisdiction_level="super")
    assert can_manage_user(superadmin, "admin", "Guntur", "district") is True


def test_plain_state_admin_cannot_create_a_state_admin():
    state_admin = _user("admin", jurisdiction_level="state")
    assert can_manage_user(state_admin, "admin", None, "state") is False


def test_plain_state_admin_can_still_create_a_district_admin():
    state_admin = _user("admin", jurisdiction_level="state")
    assert can_manage_user(state_admin, "admin", "Guntur", "district") is True


def test_district_admin_cannot_create_any_admin():
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur")
    assert can_manage_user(district_admin, "admin", "Guntur", "district") is False


def test_district_admin_can_create_staff_in_their_own_district_only():
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur")
    assert can_manage_user(district_admin, "staff", "Guntur", "district") is True
    assert can_manage_user(district_admin, "staff", "Kakinada", "district") is False


def test_staff_cannot_create_anyone():
    staff = _user("staff", jurisdiction_level="district", district="Guntur")
    assert can_manage_user(staff, "staff", "Guntur", "district") is False


# --- can_reassign_officer: the superadmin is untouchable ------------------

def test_no_one_can_reassign_the_superadmin_not_even_a_state_admin():
    superadmin = _user("admin", jurisdiction_level="super", id=1)
    state_admin_actor = _user("admin", jurisdiction_level="state", id=2)
    assert can_reassign_officer(state_admin_actor, superadmin, "staff", "Guntur") is False


def test_superadmin_can_reassign_a_district_admin():
    superadmin = _user("admin", jurisdiction_level="super", id=1)
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur", id=2)
    assert can_reassign_officer(superadmin, district_admin, "admin", "Guntur") is True


def test_district_admin_cannot_reassign_another_admin():
    district_admin_actor = _user("admin", jurisdiction_level="district", district="Guntur", id=1)
    other_district_admin = _user("admin", jurisdiction_level="district", district="Guntur", id=2)
    assert can_reassign_officer(district_admin_actor, other_district_admin, "admin", "Guntur") is False


def test_district_admin_can_reassign_their_own_staff():
    district_admin_actor = _user("admin", jurisdiction_level="district", district="Guntur", id=1)
    staff = _user("staff", jurisdiction_level="district", district="Guntur", id=2)
    assert can_reassign_officer(district_admin_actor, staff, "staff", "Guntur") is True


# --- can_delete_officer: who may delete an admin account -------------------

def test_no_one_can_delete_the_superadmin():
    superadmin = _user("admin", jurisdiction_level="super", id=1)
    state_admin_actor = _user("admin", jurisdiction_level="state", id=2)
    assert can_delete_officer(state_admin_actor, superadmin) is False
    assert can_delete_officer(superadmin, superadmin) is False


def test_superadmin_can_delete_a_district_admin():
    superadmin = _user("admin", jurisdiction_level="super", id=1)
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur", id=2)
    assert can_delete_officer(superadmin, district_admin) is True


def test_state_admin_can_delete_a_district_admin():
    state_admin = _user("admin", jurisdiction_level="state", id=1)
    district_admin = _user("admin", jurisdiction_level="district", district="Guntur", id=2)
    assert can_delete_officer(state_admin, district_admin) is True


def test_state_admin_cannot_delete_another_state_admin():
    state_admin_actor = _user("admin", jurisdiction_level="state", id=1)
    other_state_admin = _user("admin", jurisdiction_level=None, id=2)
    assert can_delete_officer(state_admin_actor, other_state_admin) is False


def test_district_admin_cannot_delete_any_admin():
    district_admin_actor = _user("admin", jurisdiction_level="district", district="Guntur", id=1)
    other_district_admin = _user("admin", jurisdiction_level="district", district="Kakinada", id=2)
    assert can_delete_officer(district_admin_actor, other_district_admin) is False
