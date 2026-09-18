from sqlalchemy.orm import Session
from app.models.notification import Notification


def create_notification(db: Session, user_id: int, title: str, body: str = None, link: str = None, issue_id: int = None):
    """
    Creates an in-portal notification for a user. Called alongside emails
    whenever something transactional happens (certificate issued,
    application approved/rejected, new chat message, account created) so
    the person sees it in the portal even if the email is delayed or the
    inbox isn't checked - keeps the two channels in sync for transparency.
    issue_id is set for anything related to an Issue (a reply, or a new
    AI-assistant escalation) so nav-count queries can trace it back.
    """
    notification = Notification(user_id=user_id, title=title, body=body, link=link, issue_id=issue_id)
    db.add(notification)
    # Deliberately does not commit - caller commits as part of its own
    # transaction, so the notification and the underlying change save atomically.
    return notification
