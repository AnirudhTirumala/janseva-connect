"""
Run this from the backend folder to check whether your .env file has real
credentials or still has the example placeholder text. It never prints your
full secrets - only enough characters to confirm they look real, plus a
pass/fail against the known placeholder strings.

Usage:
    cd backend
    python check_env.py
"""
import os
from pathlib import Path

env_path = Path(".env")

if not env_path.exists():
    print("FAIL: No .env file found in this folder.")
    print("      Run:  copy .env.example .env")
    print("      ...then edit .env with your real values.")
    raise SystemExit(1)

# Load .env manually (no dependency needed for this standalone check)
values = {}
for line in env_path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, val = line.partition("=")
    values[key.strip()] = val.strip()

# Every value .env.example ships as a stand-in. These must stay in step with
# that file: a placeholder this list does not recognise is reported as
# "configured", which is precisely the false all-clear this script exists to
# prevent. Matching is case-insensitive and covers each variant that has
# appeared in .env.example over time.
PLACEHOLDERS = {
    "SECRET_KEY": ["change-this-to-a-long-random-string"],
    "GROQ_API_KEY": ["your-groq-api-key", "your-groq-api-key-here"],
    "SMTP_USER": ["your-email@example.com", "your-email@gmail.com"],
    "SMTP_PASSWORD": ["your-email-app-password", "your-16-char-app-password"],
    "DATABASE_URL": ["postgresql://user:password@host:5432/panchayat_db"],
    "CORS_ORIGINS": ["https://your-frontend.onrender.com"],
    "ALLOWED_HOSTS": ["your-backend.onrender.com"],
}


def is_placeholder(key, value):
    candidates = PLACEHOLDERS.get(key, [])
    return any(value.strip().lower() == c.lower() for c in candidates)


def mask(s):
    if len(s) <= 6:
        return "*" * len(s)
    return s[:4] + "*" * (len(s) - 6) + s[-2:]


print("--- Checking backend/.env ---\n")

ok = True

groq = values.get("GROQ_API_KEY", "")
if not groq or is_placeholder("GROQ_API_KEY", groq):
    print("GROQ_API_KEY   : FAIL - still the placeholder (or empty)")
    ok = False
elif not groq.startswith("gsk_"):
    print(f"GROQ_API_KEY   : WARNING - doesn't start with 'gsk_' ({mask(groq)}) - double check you copied the whole key")
    ok = False
else:
    print(f"GROQ_API_KEY   : looks OK ({mask(groq)}, {len(groq)} chars)")

groq_model = values.get("GROQ_MODEL", "").strip() or "openai/gpt-oss-120b (default)"
print(f"GROQ_MODEL     : {groq_model}")
print("               -> if the AI Assistant says 'temporarily unavailable', this model may")
print("                  have been retired. Check https://console.groq.com/docs/deprecations")

smtp_user = values.get("SMTP_USER", "")
if not smtp_user or is_placeholder("SMTP_USER", smtp_user):
    print("SMTP_USER      : FAIL - still the placeholder (or empty)")
    ok = False
else:
    print(f"SMTP_USER      : looks OK ({mask(smtp_user)})")

smtp_pass = values.get("SMTP_PASSWORD", "")
if not smtp_pass or is_placeholder("SMTP_PASSWORD", smtp_pass):
    print("SMTP_PASSWORD  : FAIL - still the placeholder (or empty)")
    ok = False
elif " " in smtp_pass:
    print("SMTP_PASSWORD  : WARNING - contains a space. Gmail shows the app password with spaces"
          " for readability, but you must remove them when pasting into .env")
    ok = False
elif len(smtp_pass) != 16:
    print(f"SMTP_PASSWORD  : WARNING - is {len(smtp_pass)} chars, Gmail app passwords are normally 16")
    ok = False
else:
    print(f"SMTP_PASSWORD  : looks OK ({mask(smtp_pass)}, {len(smtp_pass)} chars)")

print()
print("All good - restart uvicorn now." if ok else "Fix the FAIL/WARNING lines above, save .env, then restart uvicorn.")
