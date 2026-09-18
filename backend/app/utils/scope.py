"""One place for Andhra Pradesh jurisdiction and visibility rules."""
from sqlalchemy.orm import Query
from sqlalchemy import or_, and_

from app.models.member import Member
from app.models.user import User


def is_superadmin(user: User) -> bool:
    """The single platform-owner account: full control, unrestricted by district,
    the only role that may appoint another state administrator."""
    return user.role == "admin" and user.jurisdiction_level == "super"


def is_state_admin(user: User) -> bool:
    # Blank level means a pre-jurisdiction admin account, which is the state
    # administrator when upgrading an existing portal. The superadmin is also
    # a state admin for every jurisdiction/scope purpose below (unrestricted
    # access everywhere a state admin has it, plus more) - is_superadmin()
    # above is the narrower check for superadmin-only actions.
    return user.role == "admin" and (user.jurisdiction_level in (None, "", "state") or is_superadmin(user))


def is_district_admin(user: User) -> bool:
    return user.role == "admin" and not is_state_admin(user)


def can_access_location(user: User, district: str | None, mandal: str | None) -> bool:
    """Whether a staff/admin officer's jurisdiction covers a given district/mandal.
    Shared by can_access_member and by any model that stores its own
    district/mandal directly (e.g. Issue) instead of joining through Member."""
    if is_state_admin(user):
        return True
    if user.role not in ("staff", "admin"):
        return False
    # Legacy staff records do not yet have a jurisdiction. Keep their
    # existing access while an existing installation is migrated; newly
    # provisioned staff always have one and are restricted below.
    if not user.district:
        return True
    if user.district != district:
        return False
    # Mandal staff can only access their own mandal. District staff and a
    # district admin can work across their assigned district.
    return user.jurisdiction_level != "mandal" or user.mandal == mandal


def can_access_member(user: User, member: Member) -> bool:
    if user.role not in ("staff", "admin"):
        return member.user_id == user.id
    return can_access_location(user, member.district, member.mandal)


def scope_members(query: Query, user: User) -> Query:
    if is_state_admin(user):
        return query
    if user.role not in ("staff", "admin"):
        return query.filter(Member.user_id == user.id)
    if not user.district:
        return query
    query = query.filter(Member.district == user.district)
    if user.jurisdiction_level == "mandal":
        query = query.filter(Member.mandal == user.mandal)
    return query


def scope_by_location(query: Query, user: User, model) -> Query:
    """Generic version of scope_members for models that store district/mandal
    directly (e.g. Issue) rather than joining through Member. Assumes the
    caller has already restricted citizen callers to their own rows."""
    if is_state_admin(user):
        return query
    if not user.district:
        return query
    query = query.filter(model.district == user.district)
    if user.jurisdiction_level == "mandal":
        query = query.filter(model.mandal == user.mandal)
    return query


def scope_issues_for_officer(query: Query, user: User, model) -> Query:
    """Scope Issue rows for staff/admins, with one deliberate exception.

    AI-reported application/certificate/service problems are shared with the
    entire service team by product policy. They remain location-tagged for
    context, but every active officer can see and route them. Portal bugs are
    *not* included in this exception: those stay with state/super admins.
    """
    if is_state_admin(user) or not user.district:
        return query

    local_scope = model.district == user.district
    if user.jurisdiction_level == "mandal":
        local_scope = and_(local_scope, model.mandal == user.mandal)

    shared_service_issue = and_(
        model.source == "ai_assistant",
        model.category == "application",
    )
    return query.filter(or_(local_scope, shared_service_issue))


def officers_for_location(query: Query, district: str | None, mandal: str | None) -> Query:
    """All active officers who are permitted to act on a request from the given district/mandal.
    "super" is included alongside "state" here (not just via is_state_admin's
    Python-level OR) because this builds a raw SQL predicate over many rows
    at once rather than checking one already-loaded User object - without it,
    a superadmin account (jurisdiction_level="super", no district) silently
    never matched the district-scoped branch below and was skipped by every
    notification that uses this helper (new applications, new citizen
    messages, civic issues)."""
    query = query.filter(User.role.in_(("staff", "admin")), User.is_active == True)  # noqa: E712
    return query.filter(or_(
        User.jurisdiction_level.is_(None),
        User.jurisdiction_level.in_(("", "state", "super")),
        and_(
            User.district == district,
            or_(User.jurisdiction_level != "mandal", User.mandal == mandal),
        ),
    ))


def can_access_channel(user: User, district: str | None, mandal: str | None) -> bool:
    """Whether `user` (staff/admin) may read or post in a given team-chat
    channel. district=None means the all-staff/all-admins broadcast
    channel, reachable only by a state/super admin (everyone still
    receives what's posted there, they just can't open the picker and
    post into it themselves). A district channel (mandal=None) is
    reachable by that district's own staff/admin and by every mandal
    within it; a mandal channel is reachable by that mandal's own staff
    plus that district's staff/admin, who have oversight across every
    mandal in their district."""
    if is_state_admin(user):
        return True
    if not district:
        return False
    if user.district != district:
        return False
    return user.jurisdiction_level != "mandal" or user.mandal == mandal


def can_access_internal_scope(user: User, scope: str, district: str | None = None, mandal: str | None = None) -> bool:
    """Permission boundary for the named staff-chat channels.

    Leadership is deliberately small (superadmin + state administrators),
    while the district-admin forum includes the next management level.  The
    geographic channels remain the working groups for the actual staff in a
    district or mandal.
    """
    if user.role not in ("staff", "admin"):
        return False
    if scope == "leadership":
        return is_state_admin(user)
    if scope == "district_admins":
        return is_state_admin(user) or is_district_admin(user)
    if scope in ("district", "mandal"):
        return can_access_channel(user, district, mandal)
    return False


def officer_users_for_member(query: Query, member: Member) -> Query:
    """All active officers who are permitted to act on a member's request."""
    return officers_for_location(query, member.district, member.mandal)


def can_manage_user(actor: User, role: str, district: str | None, level: str | None) -> bool:
    if not actor.role == "admin":
        return False
    if is_superadmin(actor):
        # Full platform control, including appointing another state admin.
        return True
    if is_state_admin(actor):
        # Only the superadmin may create another state administrator; a
        # (non-super) state admin may still create district administrators.
        return role != "admin" or level == "district"
    return role in ("staff", "citizen") and bool(actor.district) and actor.district == district


def can_delete_officer(actor: User, target: User) -> bool:
    """Whether `actor` may permanently delete `target`'s ADMIN account
    (staff and citizen deletion follow the simpler existing district-scope
    check in delete_user and never reach this function). The superadmin may
    delete any other admin; a state admin may delete a district admin but
    not another state admin or the superadmin; a district admin may never
    delete another admin."""
    if is_superadmin(target):
        return False
    if is_superadmin(actor):
        return True
    return is_state_admin(actor) and not is_state_admin(target)


def can_reassign_officer(actor: User, target: User, new_role: str, new_district: str | None) -> bool:
    """Whether `actor` may change `target`'s role/jurisdiction to the given
    new role and district. Mirrors can_manage_user's existing boundary:
    only the state administrator may promote someone into the admin role.
    A district admin may reassign staff (never admins, never themselves
    into a different district) but only staff already within, and staying
    within, their own district. The superadmin can never be reassigned by
    anyone through this endpoint - self-reassignment is already blocked by
    the router, and no one else outranks them."""
    if is_superadmin(target):
        return False
    if actor.role != "admin" or target.role == "citizen":
        return False
    if new_role == "admin" and not is_state_admin(actor):
        return False
    if is_state_admin(actor):
        # A state admin has broad operational scope but cannot change a peer
        # state administrator.  Only the superadmin may alter that tier.
        if target.role == "admin" and is_state_admin(target) and not is_superadmin(actor):
            return False
        return True
    if target.role != "staff" or not actor.district:
        return False
    return target.district == actor.district and new_district == actor.district
