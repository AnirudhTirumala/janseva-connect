"""Deletion that respects foreign keys and official-record retention.

``db.delete(user)`` on its own is only safe on SQLite, where foreign keys
are not enforced by default.  On PostgreSQL - the supported production
database - every row still pointing at that ``users.id`` raises
``ForeignKeyViolation`` and the request becomes a 500.  The same applies
to deleting a ``Member`` that already has applications or certificates.

The policy implemented here, in one place so every caller agrees:

* Nullable references are unlinked (set to NULL).  The household record,
  scheme applications, and issued certificates survive the deletion of a
  login exactly as the API docstrings promise.
* Personal rows that cannot exist without their owner - notifications,
  chat messages, raised issues, certificate requests - are removed with
  the account.
* An account that is the recorded author of a formal official act (it
  issued a certificate, or submitted a district weekly report) is NOT
  deletable.  Erasing it would leave an unattributable official record,
  so the caller is told to deactivate the account instead, which is
  already a first-class action in the UI.
"""

from sqlalchemy.orm import Session

from app.models.application import SchemeApplication
from app.models.application_document import ApplicationDocument
from app.models.certificate import Certificate
from app.models.certificate_request import CertificateRequest
from app.models.internal_message import InternalMessage
from app.models.issue import Issue
from app.models.member import Member
from app.models.message import Message
from app.models.notification import Notification
from app.models.user import User
from app.models.weekly_activity import WeeklyActivity


class RetainedRecordError(Exception):
    """Raised when deleting would orphan a record that must stay attributable."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def assert_user_is_deletable(db: Session, user: User) -> None:
    """Refuse a hard delete that would strand an official act."""
    if db.query(Certificate.id).filter(Certificate.issued_by_id == user.id).first():
        raise RetainedRecordError(
            "This account issued official certificates, which must stay attributable. "
            "Deactivate the account instead - that blocks sign-in while keeping the record intact."
        )
    if db.query(WeeklyActivity.id).filter(WeeklyActivity.submitted_by_id == user.id).first():
        raise RetainedRecordError(
            "This account submitted formal weekly reports, which must stay attributable. "
            "Deactivate the account instead - that blocks sign-in while keeping the record intact."
        )


def delete_user_record(db: Session, user: User) -> None:
    """Delete a login and everything that cannot outlive it.

    Does not commit - the caller commits as part of its own transaction,
    matching the convention used by create_notification and log_event.
    """
    assert_user_is_deletable(db, user)
    user_id = user.id

    # 1. Unlink every nullable reference so official history survives.
    db.query(Member).filter(Member.user_id == user_id).update(
        {Member.user_id: None}, synchronize_session=False
    )
    db.query(Member).filter(Member.created_by_staff_id == user_id).update(
        {Member.created_by_staff_id: None}, synchronize_session=False
    )
    db.query(SchemeApplication).filter(SchemeApplication.reviewed_by_id == user_id).update(
        {SchemeApplication.reviewed_by_id: None}, synchronize_session=False
    )
    db.query(ApplicationDocument).filter(ApplicationDocument.reviewed_by_id == user_id).update(
        {ApplicationDocument.reviewed_by_id: None}, synchronize_session=False
    )
    db.query(CertificateRequest).filter(CertificateRequest.reviewed_by_id == user_id).update(
        {CertificateRequest.reviewed_by_id: None}, synchronize_session=False
    )
    db.query(Issue).filter(Issue.replied_by_id == user_id).update(
        {Issue.replied_by_id: None}, synchronize_session=False
    )

    # 2. Remove rows that are meaningless - and unresolvable - without the account.
    #    Notifications must go first: they carry an FK to issues.
    issue_ids = [row[0] for row in db.query(Issue.id).filter(Issue.citizen_user_id == user_id).all()]
    db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
    if issue_ids:
        db.query(Notification).filter(Notification.issue_id.in_(issue_ids)).delete(synchronize_session=False)
        db.query(Issue).filter(Issue.id.in_(issue_ids)).delete(synchronize_session=False)

    db.query(Message).filter(
        (Message.citizen_user_id == user_id) | (Message.sender_id == user_id)
    ).delete(synchronize_session=False)
    db.query(InternalMessage).filter(InternalMessage.sender_id == user_id).delete(synchronize_session=False)
    db.query(CertificateRequest).filter(CertificateRequest.requested_by_id == user_id).delete(
        synchronize_session=False
    )

    db.flush()
    db.delete(user)


def member_deletion_blocker(db: Session, member: Member) -> str | None:
    """Why this household record cannot be hard-deleted, or None if it can be.

    A member with applications or certificates is the subject of official
    service history.  Deleting it would either orphan or silently destroy
    that history, so the API rejects it with an explanation rather than
    failing with a foreign-key 500.
    """
    if db.query(Certificate.id).filter(Certificate.member_id == member.id).first():
        return (
            "This household record has issued certificates linked to it and cannot be deleted. "
            "Correct the record instead so the certificate history stays valid."
        )
    if db.query(SchemeApplication.id).filter(SchemeApplication.member_id == member.id).first():
        return (
            "This household record has scheme applications linked to it and cannot be deleted. "
            "Correct the record instead so the application history stays valid."
        )
    if db.query(CertificateRequest.id).filter(CertificateRequest.member_id == member.id).first():
        return (
            "This household record has certificate requests linked to it and cannot be deleted. "
            "Resolve those requests first if the record is genuinely a duplicate."
        )
    # members.family_head_id is a self-referential foreign key. Deleting a
    # family head while other household members still point at it is a
    # ForeignKeyViolation on PostgreSQL - a 500 instead of this explanation.
    if db.query(Member.id).filter(Member.family_head_id == member.id).first():
        return (
            "Other household members are linked to this record as their family head. "
            "Reassign or remove them first."
        )
    return None
