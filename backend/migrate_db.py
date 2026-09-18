"""
One-time migration for databases created before the OTP-verified
registration feature was added. Safely adds the missing columns to the
email_otps table WITHOUT touching any existing data in any table.

Also promotes admin@panchayat.gov.in to superadmin if it's still a plain
state admin (see the "One-time promotion" block below) - safe to run even
if that account doesn't exist or was already promoted.

Safe to run multiple times - it checks which columns already exist first.

Usage:
    cd backend
    python migrate_db.py
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path("panchayat.db")

NEW_COLUMNS = {
    "pending_full_name": "TEXT",
    "pending_phone": "TEXT",
    "pending_hashed_password": "TEXT",
    "pending_role": "TEXT",
    "code_hash": "TEXT",
    "pending_jurisdiction_level": "TEXT",
    "pending_district": "TEXT",
    "pending_mandal": "TEXT",
    "pending_village": "TEXT",
    "pending_member_profile": "TEXT",
}

USER_COLUMNS = {
    "jurisdiction_level": "TEXT",
    "district": "TEXT",
    "mandal": "TEXT",
    "village": "TEXT",
    "session_version": "INTEGER NOT NULL DEFAULT 0",
}

ISSUE_COLUMNS = {
    "citizen_feedback": "TEXT",
    "citizen_responded_at": "DATETIME",
    "category": "TEXT NOT NULL DEFAULT 'civic'",
    "source": "TEXT NOT NULL DEFAULT 'citizen'",
}

NOTIFICATION_COLUMNS = {
    "issue_id": "INTEGER REFERENCES issues(id)",
}

CERTIFICATE_REQUESTS_SQL = """
CREATE TABLE IF NOT EXISTS certificate_requests (
    id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id),
    requested_by_id INTEGER NOT NULL REFERENCES users(id),
    certificate_type TEXT NOT NULL,
    purpose TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    review_remarks TEXT,
    reviewed_by_id INTEGER REFERENCES users(id),
    reviewed_at DATETIME,
    certificate_id INTEGER UNIQUE REFERENCES certificates(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

CERTIFICATE_TYPES_SQL = """
CREATE TABLE IF NOT EXISTS certificate_types (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    prefix TEXT NOT NULL DEFAULT 'CRT',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

WEEKLY_ACTIVITIES_SQL = """
CREATE TABLE IF NOT EXISTS weekly_activities (
    id INTEGER PRIMARY KEY,
    district TEXT NOT NULL,
    week_start DATE NOT NULL,
    summary TEXT NOT NULL,
    achievements TEXT,
    blockers TEXT,
    submitted_by_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

INTERNAL_MESSAGES_SQL = """
CREATE TABLE IF NOT EXISTS internal_messages (
    id INTEGER PRIMARY KEY,
    district TEXT NOT NULL,
    mandal TEXT,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

# This script speaks SQLite and only SQLite (PRAGMA table_info, sqlite_master,
# SQLite's forgiving ALTER TABLE). Production runs on PostgreSQL, where every
# statement below is either invalid or applied to the wrong database, so say
# so plainly instead of exiting 0 and letting a deployer believe a PostgreSQL
# schema was just migrated.
_configured_db_url = os.getenv("DATABASE_URL", "")
if _configured_db_url and not _configured_db_url.startswith("sqlite"):
    print("DATABASE_URL points at a non-SQLite database:")
    print(f"  {_configured_db_url.split('://')[0]}://...")
    print()
    print("This script only migrates a local SQLite panchayat.db file and would")
    print("NOT touch that database. For a brand-new PostgreSQL/MySQL deployment,")
    print("the schema is created automatically on first backend start - just run")
    print("seed.py. For an existing one, apply schema changes with your own")
    print("migration tooling and review them before running against live data.")
    raise SystemExit(1)

if not DB_PATH.exists():
    print(f"No {DB_PATH} found in this folder - nothing to migrate.")
    print("(If this is a brand new setup, just run seed.py instead - it creates the correct schema from scratch.)")
    raise SystemExit(0)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

added = []
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_otps'")
if cur.fetchone():
    cur.execute("PRAGMA table_info(email_otps)")
    existing_columns = {row[1] for row in cur.fetchall()}
    for col_name, col_type in NEW_COLUMNS.items():
        if col_name not in existing_columns:
            cur.execute(f"ALTER TABLE email_otps ADD COLUMN {col_name} {col_type}")
            added.append(col_name)
    # Older releases used this transient column to email a temporary
    # password. Clear every value during the hardening migration; newly
    # created OTPs no longer write plaintext passwords at all.
    if "pending_plain_password" in existing_columns:
        cur.execute("UPDATE email_otps SET pending_plain_password = NULL WHERE pending_plain_password IS NOT NULL")
cur.execute(CERTIFICATE_REQUESTS_SQL)
cur.execute(CERTIFICATE_TYPES_SQL)
cur.execute(WEEKLY_ACTIVITIES_SQL)
cur.execute(INTERNAL_MESSAGES_SQL)

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if cur.fetchone():
    cur.execute("PRAGMA table_info(users)")
    existing_user_columns = {row[1] for row in cur.fetchall()}
    for col_name, col_type in USER_COLUMNS.items():
        if col_name not in existing_user_columns:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            added.append(f"users.{col_name}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issues'")
if cur.fetchone():
    cur.execute("PRAGMA table_info(issues)")
    existing_issue_columns = {row[1] for row in cur.fetchall()}
    for col_name, col_type in ISSUE_COLUMNS.items():
        if col_name not in existing_issue_columns:
            cur.execute(f"ALTER TABLE issues ADD COLUMN {col_name} {col_type}")
            added.append(f"issues.{col_name}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
if cur.fetchone():
    cur.execute("PRAGMA table_info(notifications)")
    existing_notification_columns = {row[1] for row in cur.fetchall()}
    for col_name, col_type in NOTIFICATION_COLUMNS.items():
        if col_name not in existing_notification_columns:
            cur.execute(f"ALTER TABLE notifications ADD COLUMN {col_name} {col_type}")
            added.append(f"notifications.{col_name}")

# One-time promotion: the original seeded admin@panchayat.gov.in account was
# always meant to be the platform's superadmin, not a regular state admin -
# upgrade it in place (only if it's still a plain state admin, so this never
# overwrites a jurisdiction someone deliberately set by hand). Everything
# else about the account - password, other accounts, all other data - is
# untouched.
promoted_superadmin = False
cur.execute("SELECT id, role, jurisdiction_level FROM users WHERE email = 'admin@panchayat.gov.in'")
admin_row = cur.fetchone()
if admin_row and admin_row[1] == "admin" and admin_row[2] in (None, "", "state"):
    cur.execute("UPDATE users SET jurisdiction_level = 'super' WHERE id = ?", (admin_row[0],))
    promoted_superadmin = True

conn.commit()
conn.close()

print(f"Migration complete. OTP columns added: {', '.join(added) if added else 'none'}; certificate request queue is ready.")
if promoted_superadmin:
    print("admin@panchayat.gov.in promoted to superadmin (was a state admin).")
