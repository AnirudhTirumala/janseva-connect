"""Decides when a successful sign-in deserves a security email.

Emailing on *every* sign-in is the obvious implementation and the wrong one.
A mandal clerk signing in each morning would get one mail a day, learn within
a week to delete them unread, and miss the single alert that actually matters.
Alert fatigue makes the feature worse than not having it.

So the alert fires only for a sign-in from a device/network this account has
not used before. That is the standard bank/Google behaviour and it is the
only version a person will still read in six months.

No new columns are needed: audit_events already records every successful
login, and this module just gives it an ip_address/user_agent to remember and
reads them back. Set LOGIN_ALERT_MODE=always in the environment to email on
every sign-in instead (useful for a demo, noisy in real use).
"""

import hashlib
import os
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.user import User

LOGIN_ACTION = "login_succeeded"


def client_fingerprint(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    """The IP and user-agent to attribute this sign-in to.

    Behind Render's load balancer the socket peer is the proxy, so the real
    client only appears in X-Forwarded-For. uvicorn is started with
    --proxy-headers, which populates request.client with the forwarded value;
    the header is read directly as a fallback for any other deployment.
    """
    if request is None:
        return None, None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Left-most entry is the original client; the rest are proxies.
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:500] or None
    return ip, user_agent


def _device_key(ip_address: Optional[str], user_agent: Optional[str]) -> str:
    """A short, stable id for one device+network pair.

    Hashed rather than stored raw so the audit trail holds no more personal
    data than it already does; it only ever needs to answer "same as before?".
    """
    raw = f"{ip_address or '-'}|{user_agent or '-'}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def is_new_signin_device(db: Session, user: User, ip_address: Optional[str], user_agent: Optional[str]) -> bool:
    """True when this account has no earlier successful login from this device."""
    if os.getenv("LOGIN_ALERT_MODE", "new_device").lower() == "always":
        return True
    key = _device_key(ip_address, user_agent)
    seen = (
        db.query(AuditEvent.id)
        .filter(
            AuditEvent.actor_user_id == user.id,
            AuditEvent.action == LOGIN_ACTION,
            AuditEvent.target_id == key,
        )
        .first()
    )
    return seen is None


def signin_audit_fields(ip_address: Optional[str], user_agent: Optional[str]) -> dict:
    """Audit-event fields for a successful login, including the device key.

    target_id carries the device fingerprint so the next sign-in can recognise
    it. The raw IP and user agent go in their own columns, which the audit
    viewer already renders.
    """
    return {
        "target_type": "signin_device",
        "target_id": _device_key(ip_address, user_agent),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }


def describe_device(user_agent: Optional[str]) -> str:
    """A short, human phrase for the alert email - not precise fingerprinting,
    just enough for someone to recognise their own machine or not."""
    if not user_agent:
        return "unknown device"
    agent = user_agent.lower()
    if "android" in agent:
        platform = "Android"
    elif "iphone" in agent or "ipad" in agent or "ios" in agent:
        platform = "iPhone/iPad"
    elif "windows" in agent:
        platform = "Windows"
    elif "mac os" in agent or "macintosh" in agent:
        platform = "Mac"
    elif "linux" in agent:
        platform = "Linux"
    else:
        platform = "Unknown system"

    if "edg/" in agent:
        browser = "Edge"
    elif "chrome" in agent and "chromium" not in agent:
        browser = "Chrome"
    elif "firefox" in agent:
        browser = "Firefox"
    elif "safari" in agent:
        browser = "Safari"
    else:
        browser = "an unrecognised browser"
    return f"{browser} on {platform}"
