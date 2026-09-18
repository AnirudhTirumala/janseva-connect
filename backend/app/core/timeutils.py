"""One consistent notion of "now" across databases.

Every timestamp column in this app is ``DateTime(timezone=True)``.  On
PostgreSQL (the supported production database) SQLAlchemy loads those
columns back as *timezone-aware* datetimes; on SQLite (local development
and the test suite) it loads them back *naive*.  Mixing the two raises
``TypeError: can't subtract offset-naive and offset-aware datetimes``,
which is how a page that works perfectly in local development can return
a 500 the moment it runs on Render.

Rules used throughout the codebase:

* ``utcnow()`` is the only source of "now" - always aware, always UTC.
* ``as_utc(value)`` normalises anything loaded from the database before
  it is compared to or subtracted from another datetime.
* ``naive_utc()`` is for the few places that must hand a naive value to
  a library that rejects aware ones (``python-jose`` timestamps).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def naive_utc() -> datetime:
    """Current UTC time without tzinfo, for libraries that require naive input."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Coerce a datetime loaded from any backend into aware UTC.

    A naive value is assumed to already be UTC, which is true for every
    value this application writes (SQLite stores what we hand it, and
    ``func.now()`` on a UTC-configured server is UTC as well).
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_ago(**delta_kwargs) -> datetime:
    """Aware UTC timestamp some interval in the past, e.g. ``utc_ago(days=30)``."""
    return utcnow() - timedelta(**delta_kwargs)
