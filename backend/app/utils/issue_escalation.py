from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.member import Member
from app.models.user import User
from app.core.timeutils import utc_ago
from app.utils.notifications import create_notification
from app.utils.scope import is_state_admin


def platform_admins(db: Session) -> list[User]:
    """Every active state-level or superadmin account - the audience for a
    platform/portal-wide technical issue, which no single district admin
    can fix and which isn't scoped to one place."""
    admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()  # noqa: E712
    return [a for a in admins if is_state_admin(a)]


def active_officers(db: Session) -> list[User]:
    """Every active staff and administrator account.

    A reported scheme/certificate/service problem is operational work, not
    only a local-portal defect. It is shared with the complete service team
    so it cannot disappear when one local office is unavailable.
    """
    return (
        db.query(User)
        .filter(User.role.in_(("staff", "admin")), User.is_active == True)  # noqa: E712
        .all()
    )


def issue_audience(db: Session, category: str) -> tuple[list[User], str]:
    """Who must hear about an issue of this category, and how to describe them.

    Shared by the AI escalation path and by a citizen raising an issue by
    hand, because the two must agree: a portal bug routed to the local mandal
    office instead of the platform administrators is a bug nobody can fix.
    """
    if category == "portal":
        return platform_admins(db), "the platform administrators"
    if category == "application":
        return active_officers(db), "all staff and administrators"
    return [], "the local office"  # civic is routed by location, see issues.py


def create_ai_issue(db: Session, reporter: User, category: str, title: str, description: str) -> tuple[Issue, str]:
    """
    Logs a problem the AI assistant recognised but could not resolve
    itself as a real, tracked Issue - reusing the same status/reply
    workflow as a manually-raised local issue - and notifies whoever
    should act on it:
      - category="portal": a technical defect in the website/app itself -
        notified to every state/super administrator, since it affects the
        whole platform and isn't any one district's to fix.
      - category="application": a stuck/incorrect application, certificate,
        or service-delivery problem - shared with every active staff/admin
        account so the whole service team can view and route it.
    Does not commit - the caller commits as part of its own request
    transaction, same convention as create_notification.
    Returns (issue, audience_label); audience_label is a short human
    description of who was notified, for the assistant's reply to reference.
    """
    village = district = mandal = None
    if reporter.role == "citizen":
        member = db.query(Member).filter(Member.user_id == reporter.id).first()
        if member:
            village, mandal, district = member.village, member.mandal, member.district
    else:
        district, mandal = reporter.district, reporter.mandal

    if category == "portal":
        # A platform bug isn't scoped to one place, even if the reporter is.
        village = district = mandal = None

    # A support exchange can span a few messages: a first short report and
    # then the exact reproduction steps. Keep that one report in one ticket
    # instead of creating a new alert on each assistant turn.
    recent_duplicate = (
        db.query(Issue)
        .filter(
            Issue.citizen_user_id == reporter.id,
            Issue.source == "ai_assistant",
            Issue.category == category,
            Issue.status.in_(("open", "in_progress", "reopened")),
            Issue.created_at >= utc_ago(minutes=20),
        )
        .order_by(Issue.created_at.desc())
        .first()
    )
    if recent_duplicate:
        details = description.strip()
        if details and details not in (recent_duplicate.description or ""):
            recent_duplicate.description = f"{recent_duplicate.description}\n\nAdditional details: {details}"[:2000]
        issue = recent_duplicate
    else:
        issue = Issue(
            citizen_user_id=reporter.id,
            title=title,
            description=description,
            village=village,
            mandal=mandal,
            district=district,
            category=category,
            source="ai_assistant",
        )
        db.add(issue)
        db.flush()

    recipients, audience_label = issue_audience(db, category)

    notif_title = "AI Assistant flagged a portal issue" if category == "portal" else "AI Assistant flagged a reported issue"
    # The first alert is sufficient. Later messages update the same Issue
    # record above, where officers can read the extra detail without being
    # flooded by duplicate notifications.
    if not recent_duplicate:
        # A citizen should see their Assistant badge change immediately too:
        # this is the durable acknowledgement behind the assistant's ticket
        # confirmation, rather than a chat-only promise.
        create_notification(
            db,
            reporter.id,
            "AI Assistant report logged",
            f"Ticket #{issue.id}: {title}",
            link="/assistant",
            issue_id=issue.id,
        )
        for officer in recipients:
            if officer.id == reporter.id:
                continue
            create_notification(db, officer.id, notif_title, f"{reporter.full_name}: {title}", link="/issues", issue_id=issue.id)

    return issue, audience_label
