from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.models.message import Message
from app.models.member import Member
from app.models.internal_message import InternalMessage
from app.models.notification import Notification
from app.schemas.message import MessageCreate, MessageOut, ConversationOut, StaffContactOut, InternalMessageCreate, InternalMessageOut
from app.utils.notifications import create_notification
from app.utils.email_client import send_new_message_email, send_team_message_email
from app.utils.scope import can_access_channel, can_access_internal_scope, can_access_location, can_access_member, officer_users_for_member, officers_for_location, scope_members, is_state_admin, is_district_admin

router = APIRouter(prefix="/api/messages", tags=["Chat"])


def _officer_may_open_thread(officer: User, citizen_member: Member | None) -> bool:
    """Whether a staff/admin account may read or post in a citizen's thread.

    A citizen who has not completed their household profile yet has no
    Member row and therefore no district. The previous check skipped
    jurisdiction entirely in that case (`... and citizen_member and ...`),
    which let any officer statewide read their conversation - and those are
    exactly the people asking for help with sensitive personal details.

    Nobody local "owns" an unassigned citizen, so the thread is treated as
    an unassigned location and run through the same rule every other
    jurisdiction check uses. can_access_location(officer, None, None) admits
    state/super admins and the un-scoped legacy staff accounts that
    app/utils/scope.py deliberately still allows through, while excluding an
    officer assigned to a specific district - who has no business reading it.
    """
    if citizen_member is None:
        return can_access_location(officer, None, None)
    return can_access_member(officer, citizen_member)


def _with_sender_info(message: Message, db: Session) -> Message:
    sender = db.query(User).filter(User.id == message.sender_id).first()
    message.sender_name = sender.full_name if sender else None
    message.sender_role = sender.role if sender else None
    return message


def _with_internal_sender_info(message: InternalMessage, db: Session) -> InternalMessage:
    sender = db.query(User).filter(User.id == message.sender_id).first()
    message.sender_name = sender.full_name if sender else None
    message.sender_role = sender.role if sender else None
    return message


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    search: Optional[str] = Query(None, description="Filter by citizen name or email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: list every citizen (not just ones who've already messaged),
    so staff can proactively start a conversation - like a shared support
    inbox with a full contact list, not just active threads. Citizens with
    an existing conversation are sorted to the top by most recent activity;
    everyone else follows alphabetically. Supports a name/email search.
    """
    citizens_query = scope_members(
        db.query(User).outerjoin(Member, Member.user_id == User.id).filter(User.role == "citizen", User.is_active == True),  # noqa: E712
        current_user,
    )
    if search:
        like = f"%{search}%"
        citizens_query = citizens_query.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))
    citizens = citizens_query.all()

    # Three aggregate queries for the whole page, not three per citizen.
    # The previous per-citizen loop issued 2N queries: on a district with a
    # few thousand citizens that is thousands of round trips for one screen.
    citizen_ids = [citizen.id for citizen in citizens]
    last_activity: dict[int, object] = {}
    latest_bodies: dict[int, str] = {}
    unread_counts: dict[int, int] = {}
    if citizen_ids:
        last_activity = dict(
            db.query(Message.citizen_user_id, func.max(Message.created_at))
            .filter(Message.citizen_user_id.in_(citizen_ids))
            .group_by(Message.citizen_user_id)
            .all()
        )
        unread_counts = dict(
            db.query(Message.citizen_user_id, func.count(Message.id))
            .filter(
                Message.citizen_user_id.in_(citizen_ids),
                Message.is_read == False,  # noqa: E712
                Message.sender_id == Message.citizen_user_id,
            )
            .group_by(Message.citizen_user_id)
            .all()
        )
        # The newest message per thread, resolved by its id (monotonic, and
        # unambiguous when two messages share a timestamp to the second).
        newest_ids = [
            row[0]
            for row in db.query(func.max(Message.id))
            .filter(Message.citizen_user_id.in_(citizen_ids))
            .group_by(Message.citizen_user_id)
            .all()
        ]
        if newest_ids:
            latest_bodies = {
                message.citizen_user_id: message.body
                for message in db.query(Message).filter(Message.id.in_(newest_ids)).all()
            }

    conversations = []
    for citizen in citizens:
        conversations.append(
            ConversationOut(
                citizen_user_id=citizen.id,
                citizen_name=citizen.full_name,
                citizen_email=citizen.email,
                last_message=latest_bodies.get(citizen.id),
                last_message_at=last_activity.get(citizen.id),
                unread_count=unread_counts.get(citizen.id, 0),
                has_conversation=citizen.id in last_activity,
            )
        )

    # Active conversations first (most recent activity first), then
    # everyone else alphabetically by name.
    conversations.sort(
        key=lambda c: (
            0 if c.has_conversation else 1,
            -(c.last_message_at.timestamp() if c.last_message_at else 0),
            c.citizen_name.lower(),
        )
    )
    return conversations


@router.get("/office-contacts", response_model=List[StaffContactOut])
def office_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("citizen")),
):
    """Citizen-safe directory: only active office names and roles, never emails or phone numbers."""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return []
    return officer_users_for_member(db.query(User), member).order_by(User.role, User.full_name).all()


@router.get("/thread/{citizen_user_id}", response_model=List[MessageOut])
def get_thread(
    citizen_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetches a conversation thread. Citizens may only fetch their own
    thread (citizen_user_id must match their own id); staff/admin can view
    any citizen's thread.
    """
    if current_user.role == "citizen" and current_user.id != citizen_user_id:
        raise HTTPException(status_code=403, detail="You can only view your own conversation")
    citizen_member = db.query(Member).filter(Member.user_id == citizen_user_id).first()
    if current_user.role != "citizen" and not _officer_may_open_thread(current_user, citizen_member):
        raise HTTPException(status_code=403, detail="You can only access conversations in your assigned jurisdiction")

    messages = (
        db.query(Message)
        .filter(Message.citizen_user_id == citizen_user_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Mark incoming messages as read for whoever is fetching (from the
    # other side of the conversation) - citizen reading marks staff
    # messages read, staff reading marks citizen messages read.
    other_side_sender = citizen_user_id if current_user.role != "citizen" else None
    if current_user.role == "citizen":
        db.query(Message).filter(
            Message.citizen_user_id == citizen_user_id,
            Message.sender_id != citizen_user_id,
            Message.is_read == False,  # noqa: E712
        ).update({"is_read": True})
    else:
        db.query(Message).filter(
            Message.citizen_user_id == citizen_user_id,
            Message.sender_id == citizen_user_id,
            Message.is_read == False,  # noqa: E712
        ).update({"is_read": True})
    db.commit()

    return [_with_sender_info(m, db) for m in messages]


@router.post("/", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sends a chat message. Citizens always post to their own thread;
    staff/admin must specify which citizen's thread they're replying to.
    """
    if current_user.role == "citizen":
        citizen_user_id = current_user.id
    else:
        if not payload.citizen_user_id:
            raise HTTPException(status_code=400, detail="citizen_user_id is required when staff/admin sends a message")
        citizen_user_id = payload.citizen_user_id
        citizen = db.query(User).filter(User.id == citizen_user_id, User.role == "citizen").first()
        if not citizen:
            raise HTTPException(status_code=404, detail="Citizen not found")
        member = db.query(Member).filter(Member.user_id == citizen.id).first()
        if not _officer_may_open_thread(current_user, member):
            raise HTTPException(status_code=403, detail="You can only message citizens in your assigned jurisdiction")

    message = Message(citizen_user_id=citizen_user_id, sender_id=current_user.id, body=payload.body)
    db.add(message)
    db.flush()

    # Notify the other side.
    if current_user.role == "citizen":
        # Notify all staff/admin so anyone can pick it up - keep it simple
        # by notifying just admins to avoid flooding every staff member.
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        staff_and_admins = officer_users_for_member(db.query(User), member).all() if member else []
        for u in staff_and_admins:
            create_notification(db, u.id, "New citizen message", payload.body[:140], link="/chat")
    else:
        citizen = db.query(User).filter(User.id == citizen_user_id).first()
        if citizen:
            create_notification(db, citizen.id, "New message from the Panchayat office", payload.body[:140], link="/chat")
            # Email can be slow or temporarily unavailable. The message is committed
            # first, and notification delivery never delays or loses a chat reply.
            background_tasks.add_task(send_new_message_email, citizen.email, citizen.full_name, payload.body[:200])

    db.commit()
    db.refresh(message)
    return _with_sender_info(message, db)


STATEWIDE_DISTRICT = "STATEWIDE"  # legacy all-staff broadcast channel
LEADERSHIP_DISTRICT = "__LEADERSHIP__"
DISTRICT_ADMINS_DISTRICT = "__DISTRICT_ADMINS__"


def _channel_link(scope: str, district: str | None, mandal: str | None) -> str:
    """Canonical Notification.link for a team-chat channel - built the same
    way whenever a message is posted (to notify recipients) and whenever a
    channel is read (to mark those notifications read again), so the two
    always agree. The frontend builds this same string client-side (from
    the AP districts/mandals data it already has) to look up per-channel
    unread counts from /internal/unread-counts."""
    if scope == "district":
        return f"/chat?scope=district&district={quote(district or '')}"
    if scope == "mandal":
        return f"/chat?scope=mandal&district={quote(district or '')}&mandal={quote(mandal or '')}"
    if scope == "leadership":
        return "/chat?scope=leadership"
    if scope == "district_admins":
        return "/chat?scope=district_admins"
    return "/chat?scope=all"


def _channel_label(scope: str, district: str | None, mandal: str | None) -> str:
    """Readable channel name for the notification email subject line."""
    if scope == "leadership":
        return "the leadership channel"
    if scope == "district_admins":
        return "the district administrators channel"
    if scope == "mandal":
        return f"the {mandal} mandal channel" if mandal else "a mandal channel"
    if scope == "district":
        return f"the {district} district channel" if district else "a district channel"
    return "the all-staff channel"


def _team_recipients(db: Session, scope: str, district: str | None, mandal: str | None):
    """The notification audience for one exact internal chat channel."""
    if scope in ("leadership", "district_admins"):
        officers = db.query(User).filter(
            User.role == "admin", User.is_active == True,  # noqa: E712
        ).all()
        if scope == "leadership":
            return [officer for officer in officers if is_state_admin(officer)]
        return [officer for officer in officers if is_state_admin(officer) or is_district_admin(officer)]
    if scope == "all":
        return db.query(User).filter(User.role.in_(("staff", "admin")), User.is_active == True).all()  # noqa: E712
    return officers_for_location(db.query(User), district, mandal).all()


@router.get("/internal", response_model=List[InternalMessageOut])
def internal_thread(
    scope: Optional[str] = None,
    district: Optional[str] = None,
    mandal: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    District/mandal working chat; administrators have transparent oversight.

    With scope=all|district|mandal, returns exactly ONE channel's messages -
    the multi-channel picker used by state/super admins (the all-staff
    channel, every district, and every mandal) and district admins/staff
    (their own district plus every mandal within it). Reading a channel
    this way also marks its notifications read - the same "visiting the
    page is how you saw it" pattern used elsewhere in the app.

    Without those params (the original behaviour, still used by mandal-level
    staff who don't get a picker), returns everything the caller's own
    jurisdiction can see, merged into one thread: a state admin's own
    messages carry district=STATEWIDE and act as a state-wide broadcast, so
    every district/mandal view includes them alongside that district's own
    messages - the same way a district-level message with mandal=None
    already reaches every mandal in that district.
    """
    if scope in ("all", "leadership", "district_admins", "district", "mandal"):
        target_district = district if scope in ("district", "mandal") else None
        target_mandal = mandal if scope == "mandal" else None
        if scope == "district" and not target_district:
            raise HTTPException(status_code=422, detail="A district is required for a district channel")
        if scope == "mandal" and not (target_district and target_mandal):
            raise HTTPException(status_code=422, detail="A district and mandal are required for a mandal channel")
        allowed = (
            can_access_internal_scope(current_user, scope, target_district, target_mandal)
            if scope in ("leadership", "district_admins")
            else can_access_channel(current_user, target_district, target_mandal)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="You don't have access to this team chat channel")

        if scope == "leadership":
            query = db.query(InternalMessage).filter(InternalMessage.district == LEADERSHIP_DISTRICT)
        elif scope == "district_admins":
            query = db.query(InternalMessage).filter(InternalMessage.district == DISTRICT_ADMINS_DISTRICT)
        elif scope == "all":
            query = db.query(InternalMessage).filter(InternalMessage.district == STATEWIDE_DISTRICT)
        elif scope == "district":
            query = db.query(InternalMessage).filter(InternalMessage.district == target_district, InternalMessage.mandal.is_(None))
        else:
            query = db.query(InternalMessage).filter(InternalMessage.district == target_district, InternalMessage.mandal == target_mandal)
        messages = query.order_by(InternalMessage.created_at.asc()).limit(500).all()

        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
            Notification.link == _channel_link(scope, target_district, target_mandal),
        ).update({"is_read": True}, synchronize_session=False)
        db.commit()
        return [_with_internal_sender_info(m, db) for m in messages]

    query = db.query(InternalMessage)
    if not is_state_admin(current_user) and current_user.district:
        query = query.filter(or_(InternalMessage.district == current_user.district, InternalMessage.district == STATEWIDE_DISTRICT))
    if current_user.role == "staff" and current_user.jurisdiction_level == "mandal" and current_user.mandal:
        query = query.filter((InternalMessage.mandal == current_user.mandal) | (InternalMessage.mandal.is_(None)))
    messages = query.order_by(InternalMessage.created_at.asc()).limit(500).all()

    # Mirrors the channel-aware branch above: mark read everything this
    # merged view could show (the all-staff channel, this officer's own
    # district channel, and - for mandal staff - their own mandal channel).
    legacy_links = [_channel_link("all", None, None)]
    if current_user.district:
        legacy_links.append(_channel_link("district", current_user.district, None))
        if current_user.jurisdiction_level == "mandal" and current_user.mandal:
            legacy_links.append(_channel_link("mandal", current_user.district, current_user.mandal))
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
        Notification.link.in_(legacy_links),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return [_with_internal_sender_info(message, db) for message in messages]


@router.post("/internal", response_model=InternalMessageOut, status_code=201)
def send_internal_message(
    payload: InternalMessageCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Posts to team chat. With scope set (the channel picker), posts to that
    exact channel after checking the sender may post there, and notifies
    everyone who can see it. Without scope (the original behaviour, still
    used by mandal-level staff), posts to the sender's own default channel:
    a state admin has no single district by design (they oversee every
    district), so their message posts as a state-wide broadcast
    (district=STATEWIDE); anyone else without a district is a data gap -
    an officer account never assigned one - and is blocked with an
    actionable message rather than silently posting somewhere no one sees.
    """
    if payload.scope in ("all", "leadership", "district_admins", "district", "mandal"):
        target_district = payload.district if payload.scope in ("district", "mandal") else None
        target_mandal = payload.mandal if payload.scope == "mandal" else None
        if payload.scope == "district" and not target_district:
            raise HTTPException(status_code=422, detail="A district is required for a district channel")
        if payload.scope == "mandal" and not (target_district and target_mandal):
            raise HTTPException(status_code=422, detail="A district and mandal are required for a mandal channel")
        allowed = (
            can_access_internal_scope(current_user, payload.scope, target_district, target_mandal)
            if payload.scope in ("leadership", "district_admins")
            else can_access_channel(current_user, target_district, target_mandal)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="You don't have permission to post in this channel")
        storage_district = {
            "all": STATEWIDE_DISTRICT,
            "leadership": LEADERSHIP_DISTRICT,
            "district_admins": DISTRICT_ADMINS_DISTRICT,
        }.get(payload.scope, target_district)
        message = InternalMessage(
            district=storage_district,
            mandal=target_mandal,
            sender_id=current_user.id,
            body=payload.body.strip(),
        )
        scope_label, lookup_district, lookup_mandal = payload.scope, target_district, target_mandal
    else:
        if not is_state_admin(current_user) and not current_user.district:
            raise HTTPException(status_code=422, detail="Assign a district to this officer before using staff collaboration chat")
        is_broadcast = is_state_admin(current_user)
        message = InternalMessage(
            district=current_user.district if not is_broadcast else STATEWIDE_DISTRICT,
            mandal=current_user.mandal if current_user.jurisdiction_level == "mandal" else None,
            sender_id=current_user.id,
            body=payload.body.strip(),
        )
        lookup_district = None if is_broadcast else current_user.district
        lookup_mandal = message.mandal
        scope_label = "all" if is_broadcast else ("mandal" if lookup_mandal else "district")

    db.add(message)
    db.flush()
    link = _channel_link(scope_label, lookup_district, lookup_mandal)
    recipients = _team_recipients(db, scope_label, lookup_district, lookup_mandal)
    channel_label = _channel_label(scope_label, lookup_district, lookup_mandal)
    for officer in recipients:
        if officer.id == current_user.id:
            continue
        create_notification(db, officer.id, "New team chat message", f"{current_user.full_name}: {payload.body[:140]}", link=link)
        if officer.email:
            # Background: team chat must not wait on a mail server, and one
            # unreachable officer's address must not fail the whole post.
            background_tasks.add_task(
                send_team_message_email, officer.email, officer.full_name,
                current_user.full_name, channel_label, payload.body[:200],
            )
    db.commit()
    db.refresh(message)
    return _with_internal_sender_info(message, db)


@router.get("/internal/unread-counts")
def internal_unread_counts(db: Session = Depends(get_db), current_user: User = Depends(require_roles("staff", "admin"))):
    """Unread count per team-chat channel, keyed by the exact link string
    each channel's messages are notified under (see _channel_link) - the
    frontend builds the same key for each channel it renders (from the AP
    districts/mandals data it already has) and looks up its count here."""
    rows = (
        db.query(Notification.link, func.count(Notification.id))
        .filter(Notification.user_id == current_user.id, Notification.is_read == False, Notification.link.like("/chat?scope=%"))  # noqa: E712
        .group_by(Notification.link)
        .all()
    )
    return {link: count for link, count in rows}


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Citizen: unread staff replies in their own thread. Staff/Admin:
    unread citizen messages scoped to their own jurisdiction, PLUS unread
    team-chat notifications across every channel they can see - previously
    only the citizen-inbox half was counted here, so the sidebar Chat badge
    silently missed every unread team message. citizen_unread/team_unread
    are also broken out so the Chat page can badge its two tabs separately."""
    if current_user.role != "citizen":
        citizen_unread = (
            scope_members(
                db.query(Message).join(Member, Member.user_id == Message.citizen_user_id), current_user,
            )
            .filter(Message.sender_id == Message.citizen_user_id, Message.is_read == False)  # noqa: E712
            .count()
        )
        team_unread = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id, Notification.is_read == False, Notification.link.like("/chat?scope=%"))  # noqa: E712
            .count()
        )
        return {"unread_count": citizen_unread + team_unread, "citizen_unread": citizen_unread, "team_unread": team_unread}

    count = (
        db.query(Message)
        .filter(
            Message.citizen_user_id == current_user.id,
            Message.sender_id != current_user.id,
            Message.is_read == False,  # noqa: E712
        )
        .count()
    )
    return {"unread_count": count}
