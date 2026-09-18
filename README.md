# JanSeva Connect — Smart Community Management Platform

A production-ready web platform that digitizes a Village Panchayat's daily
administration: member records, government scheme applications, official
certificates, and an AI assistant — replacing paper registers, handwritten
certificates, and manual monthly reports.

Built for the RURAL-IT-Hub capstone project.

## July 2026 product upgrade

- Animated JanSeva Connect public site with three citizen service cards and slide-in Home, About, Services, and Why panels.
- State Admin, district admin, district staff, and mandal staff jurisdictions for Andhra Pradesh; visibility is limited to the relevant district/mandal.
- Verified admin-led citizen onboarding: full household form, email OTP, then an emailed login ID and temporary password.
- Staff approval of scheme requests, formal district weekly reports, district/mandal collaboration chat, and an admin-managed certificate catalogue.
- Application and certificate emails for received, approved, rejected, and issued events. Final decisions are idempotent, so repeat approval requests are blocked rather than emailing again.

For an existing SQLite installation, run the safe migration once before starting the backend:

```bash
cd backend
python migrate_db.py
```

---

## 1. What this solves

| Paper-based problem | Digital solution here |
|---|---|
| Member search takes minutes, duplicate/lost records | Searchable `members` table, Aadhaar-uniqueness check |
| Certificates handwritten, error-prone, unsearchable | One-click PDF generation with a unique certificate number |
| Scheme applications untrackable, no approval history | Full application lifecycle (`pending → under_review → approved/rejected`) with reviewer + timestamp audit trail |
| Monthly reports take hours to compile by hand | `/api/dashboard/summary` aggregate stats + AI-written report narrative |
| Staff manually answer "what am I eligible for?" | AI Assistant chat grounded in the live scheme catalog |

## 2. Architecture

```
┌─────────────────────┐        JWT (Bearer) auth        ┌──────────────────────┐
│   React + Vite SPA   │ ───────────────────────────────▶│   FastAPI backend    │
│   (Tailwind CSS)     │◀─────────────────────────────── │   (SQLAlchemy ORM)   │
└─────────────────────┘         REST JSON API            └──────────┬───────────┘
                                                                      │
                                                          ┌───────────┴───────────┐
                                                          │  PostgreSQL (prod)    │
                                                          │  SQLite (local dev)   │
                                                          └───────────────────────┘
                                                                      │
                                                          ┌───────────┴───────────┐
                                                          │  Groq API (Llama 3.3) │
                                                          │  AI Assistant features│
                                                          └───────────────────────┘
```

**Four roles, one codebase:** `citizen`, `staff`, `admin`, `superadmin`.
Every API route enforces role and jurisdiction checks server-side — the
frontend nav is just a convenience, not a security boundary.

## 3. Database design

- **users** — login identity for all 4 roles (email + hashed password + role)
- **members** — the digitized household register; optionally linked to a `users` row via `user_id` so a citizen can see their own record
- **schemes** — admin-managed catalog of welfare programs
- **scheme_applications** — one row per citizen-scheme application, tracks status + reviewer + remarks
- **scheme_document_requirements** — the list of documents a scheme needs (e.g. "Aadhaar Card", "Income Proof"), each defined separately by admin so citizens get one upload slot per document, not one bundled file
- **application_documents** — one row per uploaded file against a specific requirement, with its own independent approve/reject status and reviewer
- **certificates** — one row per issued certificate, with a unique certificate number and a path to the generated PDF
- **email_otps** — short-lived 6-digit codes for registration verification and password reset via email

- **audit_events** stores append-only click, login, and API action history, including the actor, outcome, and timestamp. It never stores passwords, OTP values, or document contents.

See `backend/app/models/` for full field definitions and relationships.

## 4. Tech stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, python-jose (JWT), passlib/bcrypt, ReportLab (PDF), Groq SDK
- **Frontend:** React 18, Vite, React Router, Tailwind CSS, Recharts, lucide-react, axios
- **Database:** SQLite for local dev; PostgreSQL or MySQL in production
- **AI:** Groq free tier, `llama-3.3-70b-versatile`
- **Deployment target:** Render (backend web service + static frontend + managed Postgres)

### MySQL configuration

1. Create an empty MySQL database with UTF-8 support.
2. Install backend dependencies (`pip install -r requirements.txt`).
3. Set `DATABASE_URL` in `backend/.env` or your hosting provider to:

```env
DATABASE_URL=mysql+pymysql://YOUR_USER:YOUR_PASSWORD@YOUR_HOST:3306/panchayat_db?charset=utf8mb4
```

On startup, SQLAlchemy creates the full schema, including users, OTP history, citizen/staff/admin records, applications, certificate decisions, and the audit trail. Keep the default SQLite URL only for local demos.

## 5. Project structure

```
panchayat-platform/
├── backend/
│   ├── app/
│   │   ├── core/          # config, database session, JWT/security, auth dependencies
│   │   ├── models/        # SQLAlchemy models (User, Member, Scheme, SchemeApplication, Certificate)
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # API endpoints, grouped by resource
│   │   ├── utils/         # PDF generation, AI client wrapper
│   │   └── main.py        # FastAPI app, CORS, router registration
│   ├── seed.py             # creates demo admin/staff accounts + sample schemes
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/            # axios client + grouped endpoint functions
    │   ├── context/        # AuthContext (JWT session state)
    │   ├── components/     # Layout (sidebar), ProtectedRoute, StatusBadge
    │   └── pages/           # Login, Register, Dashboard, Members, Schemes,
    │                        # Applications, Certificates, Users, AIAssistant
    ├── package.json
    └── .env.example
```

## 6. Local setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit if needed (GROQ_API_KEY etc.)
python seed.py                  # creates demo accounts + sample schemes
uvicorn app.main:app --reload   # http://localhost:8000
```

API docs (auto-generated): **http://localhost:8000/docs**

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

### Demo accounts (created by `seed.py`)

`seed.py` creates a superadmin (`admin@panchayat.gov.in`) and a district
staff account (`staff@panchayat.gov.in`), and **generates a strong random
password for each, printed once when the account is created**. Copy them
somewhere safe at that moment - nothing stores them in plaintext, so a lost
password has to go through Forgot Password.

Earlier versions seeded the fixed passwords `Admin@123` / `Staff@123`. Those
are in this repository's history and must be treated as public: if any
deployment still uses them, change them now. They no longer pass the
platform's own password policy either.

To choose your own instead of the generated ones:

```bash
SEED_ADMIN_PASSWORD='...' SEED_STAFF_PASSWORD='...' python seed.py
```

Citizens self-register from the "Create an account" link on the login page.

### The verification code never arrives

First, check whether the address can actually receive mail. The app hands the
message to your SMTP server and that server accepts it for relay, so the API
honestly reports "sent" - but a non-existent mailbox is only discovered
minutes later, when the remote server bounces it. That bounce goes to the
**sending** account (`SMTP_USER`), not to the person registering, so from
their side the code simply never comes.

A bounce reading `550 5.1.1 The email account that you tried to reach does
not exist` means the address is wrong or the mailbox is gone - no amount of
resending will help. Send a normal email to it from any mail client to
confirm; if that bounces too, it is not the portal.

To register while email is unavailable (wrong address, no SMTP configured, no
internet), run the backend with delivery switched off:

```bash
cd backend
python dev_no_email.py
```

Codes are printed in that terminal instead of emailed - look for
`[DEV MODE - OTP NOT SENT]`. Everything else works normally.

### "Something went wrong on our side" on login or registration

Almost always an out-of-date database, not a bug in the code.
`Base.metadata.create_all()` creates missing *tables* but never adds a missing
*column* to a table that already exists, so a `panchayat.db` from an earlier
version keeps its old shape and every query touching a newer column fails.

The backend now detects this at startup and prints exactly which columns are
missing. The fix:

```bash
cd backend
python migrate_db.py     # additive, safe to run twice, keeps all existing rows
```

In production the app refuses to start on a drifted schema rather than serving
an API that 500s on every sign-in.

### What the platform emails, and when

| Event | Who is emailed | Contains |
|---|---|---|
| Registration started | the new citizen | 6-digit verification code |
| Account verified / created | the new citizen or officer | confirmation + next step |
| **Sign-in from a new device or network** | the account owner | time, IP, browser/OS, what to do if it wasn't them |
| Applied for a scheme | the citizen | acknowledgement |
| Application approved / rejected | the citizen | decision **plus the officer's remarks, on both outcomes** |
| Certificate requested | the citizen | acknowledgement |
| Certificate request approved / rejected | the citizen | decision **plus the officer's remarks** |
| Certificate issued | the citizen | certificate number |
| Office replies in chat | the citizen | message preview |
| **Team chat message** | every officer in that channel | sender, channel, preview |
| **Reply on a local issue** | the citizen who raised it | new status + the office's actual words |
| Role or jurisdiction changed | the officer | old role -> new role |
| Password reset / change / account deletion | the account owner | one-time code |

Sign-in alerts fire for a **device/network not seen before on that account**,
not for every login. Emailing every sign-in trains a daily user to delete
them unread, which costs you the one alert that matters. Recognition uses the
existing `audit_events` trail, so there is no extra table. Set
`LOGIN_ALERT_MODE=always` to email on every sign-in instead.

Behind a proxy (Render), the client IP comes from `X-Forwarded-For` - which is
why the start command includes `--proxy-headers`. Without it every sign-in
looks like it came from the load balancer and no alert would ever fire.

### Password policy

Every password set anywhere in the platform (self-registration, an admin
creating an account, a reset, a change) must be at least 10 characters and
combine at least three of: lowercase letters, uppercase letters, numbers,
symbols. A short deny-list rejects the passwords that top every breach
corpus. The rule lives in `backend/app/schemas/password.py` and is mirrored
in `frontend/src/utils/passwordPolicy.js` so the form can warn before
submitting - the server remains the authority.

### Enabling the AI Assistant

The AI features (chat, letter drafting, report summaries, SQL helper) need a
free Groq API key:

1. Get one at https://console.groq.com
2. Put it in `backend/.env` as `GROQ_API_KEY=...`
3. Restart the backend

Without a key, the AI endpoints respond with a friendly "not configured yet"
message instead of erroring — the rest of the app works normally.

### Enabling email OTP verification

Email codes are used in two places, both citizen-facing:
- **Registration** — after filling name/email/phone/password, a 6-digit code is emailed to confirm the address before the account is created
- **Forgot password** (any role) — request a code by email, then set a new password

To actually send that code by email, add SMTP credentials to `backend/.env`.
The easiest free option is Gmail:

1. Turn on 2-Step Verification on the sending Gmail account
2. Create an **App Password** at https://myaccount.google.com/apppasswords
3. In `backend/.env`, set:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=the-16-char-app-password   # not your normal Gmail password
   ```
4. Restart the backend

**Without SMTP configured**, the OTP code is printed to the backend's
console instead of emailed (look for a line like
`[DEV MODE - EMAIL NOT SENT] OTP for someone@example.com: 123456`) — so you
can test the whole flow locally before setting up real email delivery.

Codes expire after 10 minutes (`OTP_EXPIRY_MINUTES` in `.env`).

Run `python check_env.py` from the `backend` folder any time to verify your
`.env` values look correct (it never prints full secrets, only masked
previews) before restarting the server.

### Document uploads on scheme applications

Admins define required documents per scheme one at a time when creating it
(e.g. "Aadhaar Card", "Income Proof", "PAN Card") — each becomes its own
separate upload slot, not one combined PDF. When a citizen applies to a
scheme with required documents, they're immediately prompted to upload each
one; they can also come back and finish later from "My Applications" →
"Manage documents".

Staff/admin review each uploaded document independently (approve/reject
with optional remarks) from Applications → "View documents" — separate
from the overall application approval, so a citizen can be asked to
re-upload just one bad document without restarting the whole application.

Accepted file types: PDF, JPG, PNG. Max size: 5 MB per document.

### Multi-language UI

The interface is available in **English, Hindi, and Telugu**, switchable
from a dropdown in the sidebar (and on the login/register screens). The
translation system is `react-i18next`, with per-language JSON files at
`frontend/src/locales/{en,hi,te}.json`.

Coverage: navigation, authentication flows (login/register/forgot
password), and the main page headers/primary actions are fully translated.
Some deeper modal/form field labels remain English-only — extending
coverage just means adding more keys to the three JSON files and wrapping
the corresponding JSX text in `t('your.key')`.



If you already have a `panchayat.db` from before the registration/forgot-password
feature was added, run this once to safely add the new columns without losing
any existing data:
```bash
cd backend
python migrate_db.py
```
Safe to run multiple times - it only adds what's missing.

## 7. Deploying to Render

**Backend (Web Service):**
1. New → Web Service → connect this repo, root directory `backend`
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add a Render PostgreSQL instance, copy its connection string into the `DATABASE_URL` env var
5. Set `SECRET_KEY`, `GROQ_API_KEY`, and `CORS_ORIGINS` (your frontend's Render URL) as env vars
6. After first deploy, run `python seed.py` once via the Render shell to create demo accounts

**Frontend (Static Site):**
1. New → Static Site → same repo, root directory `frontend`
2. Build command: `npm ci && npm run build`
3. Publish directory: `dist`
4. Set `VITE_API_URL` env var to your backend's Render URL (with `https://`).
   The build fails deliberately if it is missing, rather than shipping a
   bundle that calls `localhost`.
5. Add a rewrite of `/*` → `/index.html` (already in `render.yaml`).

**Frontend on Vercel instead:** see [frontend/DEPLOY-VERCEL.md](frontend/DEPLOY-VERCEL.md).
Set the project's Root Directory to `frontend`; `frontend/vercel.json` handles
the SPA rewrite and security headers. The **backend cannot run on Vercel** -
it needs a persistent disk and a long-lived process. Keep it on Render.

A `render.yaml` blueprint at the repo root provisions the backend, the static
site, the managed Postgres instance, and the persistent disk in one step.

## 8. Security notes

- Passwords are hashed with bcrypt, never stored in plaintext, and must pass
  the strength policy described above
- A login attempt for an unregistered address spends the same bcrypt time as
  one with a wrong password, so timing does not reveal who has an account
- JWTs are signed with `SECRET_KEY` (rotate this in production) and expire after 24h by default;
  a password change, reset, or deactivation revokes every existing token immediately
- Every write endpoint checks role **and jurisdiction** server-side, not just in the UI
- Aadhaar numbers and income figures are only ever returned to staff/admin within
  the record's own district/mandal, or to the citizen who owns the record
- Uploads are validated by file signature (not just the browser's declared type),
  capped at 5 MB while streaming, and stored under random filenames
- Unhandled errors return a generic 500; stack traces and ORM messages stay in the log
- Rate limits cover authentication, OTP, AI, and click-audit endpoints
- `.env` files are gitignored — never commit real secrets. Run
  `python check_env.py` from `backend/` to sanity-check your values (it only
  prints masked previews)

## 9. Admin scheme management, live database view, and account controls

- Admins can **edit or delete** any scheme (including its document requirements) from the Schemes page, not just create new ones.
- Certificates lists show **S.No., citizen name, certificate name, date & time issued**, and download, for both staff/admin (all certificates) and citizens (their own).
- A **Database** page (admin-only, in the sidebar) shows live structured tables for Users, Members, Schemes, Applications, Certificates, safe OTP metadata, and a read-only audit log without raw SQL. OTP codes and passwords are never exposed.
- **Citizen account deletion** requires two steps: typing "DELETE" to confirm intent, then entering a one-time code emailed to the account - deleting a login can't happen from UI text alone.
- **Admins can delete or deactivate** any staff or citizen account from Staff & Users (admin accounts are protected from deletion to avoid a locked-out office).
- The language switcher is a compact 3-button toggle (EN / हि / తె) instead of a dropdown, shown in the sidebar and on the login/register/forgot-password screens.
- The login page's demo-credential hints were removed; in their place is an "About this platform" link explaining what the platform is for and why it exists.

## 10. Known limitations / next steps

- `Base.metadata.create_all()` is used instead of Alembic migrations for new *tables*. `migrate_db.py` adds new *columns* to an existing **SQLite** file safely; it refuses to run against PostgreSQL rather than pretending to migrate it, so changing the schema of an existing production database needs migration tooling you add yourself
- Automated tests live in `backend/tests/` (103 tests: `cd backend && pytest`). `backend/e2e_api_check.py` additionally drives a running server through 106 checks across all four roles — see DEPLOYMENT.md section 5
- The AI SQL helper only *suggests* SQL — it intentionally does not execute queries automatically, to avoid an AI-generated query running unreviewed against production data
- Hindi/Telugu translation coverage is broad but not 100% exhaustive (see Multi-language UI section above) — some deeper modal text remains English-only
- Uploaded documents and generated PDFs are stored on local disk under `STORAGE_PATH`; for a real production deployment on Render, pair this with a persistent disk or move to object storage (S3-compatible), since Render's filesystem is ephemeral on redeploys
- The JWT is kept in `localStorage` — the usual SPA trade-off. It survives a refresh but is readable by any script on the page; an httpOnly cookie would remove that class of risk and is the natural next hardening step
- **This repository's history contains citizen documents.** 158 generated certificate PDFs and uploaded ID documents were committed before the `.gitignore` rules existed. They are no longer tracked, so new commits are clean, but they remain in earlier commits — purge them with `git filter-repo` before making this repository public
