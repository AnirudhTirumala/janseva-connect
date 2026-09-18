"""Detect a database whose schema is behind the models, and say so clearly.

``Base.metadata.create_all()`` creates missing *tables*. It never adds a
missing *column* to a table that already exists. So a database created by an
older version of this app keeps running with the old columns, and every query
touching a new one fails with

    sqlite3.OperationalError: no such column: users.session_version

That surfaces to the person signing in as a generic 500 - "Something went
wrong on our side" - on login, on registration, on everything, with no hint
that the cause is an unmigrated database and no mention of the script that
fixes it. Diagnosing it means reading a server traceback.

This module compares the live schema against the models at startup and turns
that into one actionable message naming the exact gaps.
"""

import logging
from typing import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.database import Base

logger = logging.getLogger("panchayat.schema")


def find_schema_gaps(engine: Engine) -> list[str]:
    """Return human-readable descriptions of tables/columns the models expect
    but the database does not have. Empty list means the schema is current."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    gaps: list[str] = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            # create_all handles whole missing tables, so this only shows up
            # if it has not run yet - still worth naming.
            gaps.append(f"table '{table_name}' is missing entirely")
            continue
        present = {column["name"] for column in inspector.get_columns(table_name)}
        missing = [column.name for column in table.columns if column.name not in present]
        if missing:
            gaps.append(f"{table_name} is missing column(s): {', '.join(sorted(missing))}")

    return gaps


def format_gap_report(gaps: Iterable[str], *, is_sqlite: bool) -> str:
    remedy = (
        "Run `python migrate_db.py` from the backend/ directory - it adds the "
        "missing columns without touching existing rows, and is safe to run twice."
        if is_sqlite else
        "Apply the corresponding schema change to this database with your migration "
        "tooling before starting the app. migrate_db.py only handles local SQLite."
    )
    return (
        "This database's schema is older than the application code.\n"
        "  " + "\n  ".join(gaps) + "\n\n"
        "Until this is fixed, requests that touch those tables fail with a generic "
        "500 error (sign-in and registration included).\n" + remedy
    )


def verify_schema_is_current(engine: Engine, *, fail_fast: bool) -> list[str]:
    """Check the schema, log a clear report, and optionally refuse to start.

    ``fail_fast`` is for production: booting an API that 500s on every login
    is worse than not booting at all, because the failure is silent and looks
    like an application bug. In development the app still starts - the
    developer may be mid-migration - but the message is impossible to miss.
    """
    try:
        gaps = find_schema_gaps(engine)
    except Exception:
        # A database that cannot even be inspected is the health check's
        # problem, not this one. Never let the check itself stop startup.
        logger.warning("Could not inspect the database schema; skipping the drift check.", exc_info=True)
        return []

    if not gaps:
        return []

    report = format_gap_report(gaps, is_sqlite=engine.url.get_backend_name() == "sqlite")
    if fail_fast:
        logger.critical("Refusing to start: %s", report)
    else:
        logger.error("DATABASE SCHEMA IS OUT OF DATE\n%s", report)
        print("\n" + "=" * 72 + f"\n  DATABASE SCHEMA IS OUT OF DATE\n\n  {report}\n" + "=" * 72 + "\n")
    return gaps
