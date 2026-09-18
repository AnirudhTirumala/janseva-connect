# Deployment & Production Readiness Checklist

> ## Before you deploy anywhere: two blocking actions
>
> **1. Rotate the credentials in `backend/.env`.** That file is committed in
> the initial commit (`git show HEAD:backend/.env`) with a live Groq API key
> and a Gmail app password. Anyone who has ever had a copy of this repository
> has them. Revoke and reissue both, and generate a fresh `SECRET_KEY`, before
> this goes near real citizen data. The file is no longer tracked going
> forward, but removing it now does not un-share what was already shared.
>
> **2. Commit the work.** A host deploys what is in the repository, not what
> is in your working directory. Several backend modules the app imports at
> startup (`app/core/timeutils.py`, `app/utils/record_deletion.py`,
> `app/schemas/password.py`, and others) are new and untracked - committing
> only the modified files would produce a backend that cannot import. Use
> `git add -A` so the new files, the deletions, and the deploy manifests all
> go in together.

This is an honest checklist, not a "it's all done" doc. Some items are code
that's already in place and just needs configuring; a couple are decisions
you need to make before going live with real citizen data.

## 1. Already handled in code (verify, don't just trust)

- [x] **Passwords hashed with bcrypt** - never stored or logged in plaintext.
- [x] **Password strength enforced server-side** - 10+ characters, at least
      three character classes, and a deny-list of the passwords that appear
      first in every breach corpus. Length alone is not a policy: `Admin@123`
      and `password123` are both rejected. The same rule is mirrored in the
      browser (`frontend/src/utils/passwordPolicy.js`) so people are told
      before they submit, not after.
- [x] **JWT auth with immediate session revocation**. All write endpoints check role server-side (not just hidden in the UI); password resets/changes and deactivation invalidate previous tokens.
- [x] **Rate limiting** on every auth-adjacent endpoint (login, register, OTP request/verify,
      password reset, change password, account deletion), on the AI endpoints
      (they bill a third-party provider), and on click auditing.
- [x] **Account enumeration resistance** - a login for an address with no
      account spends the same bcrypt work as one with a wrong password, so
      response timing does not reveal who is registered.
- [x] **SECRET_KEY enforcement** - the app refuses to start in `ENVIRONMENT=production`
      if `SECRET_KEY` is missing or under 32 characters. It also refuses SQLite,
      a missing `STORAGE_PATH`, unset SMTP credentials, and any non-HTTPS or
      wildcard CORS origin.
- [x] **Security headers** (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
      `Referrer-Policy`, `Permissions-Policy`, plus HSTS and CSP in production)
      on every response.
- [x] **No internal detail in error responses** - an unhandled exception is
      logged server-side and returns a generic 500, rather than echoing ORM
      errors, table names, or a stack trace to the caller.
- [x] **SQL injection**: not applicable - everything goes through the SQLAlchemy ORM,
      no raw string-built queries anywhere in the codebase.
- [x] **File upload validation**: PDF/JPG/PNG allowlist, signature validation (not only browser-supplied MIME type), a 5 MB cap enforced *while reading* (an oversized body is rejected mid-stream, never buffered whole), random safe filenames, and path containment checks on download.
- [x] **OTP protection**: cryptographically generated codes, HMAC-hashed at rest, one active code per flow, and rate limits on every request/confirmation endpoint. No plaintext temporary password is stored or sent by email.
- [x] **Rejections require a reason** - enforced at the schema level (422 if you try to
      reject without remarks), not just a frontend nicety.
- [x] **Input bounds match the database** - every string field is validated
      against its actual column width. On SQLite an over-long value is stored
      silently; on PostgreSQL it is a hard `DataError`, so these are returned
      as a 422 the form can show instead of a 500.
- [x] **Timezone-correct timestamps** - all comparisons go through
      `app/core/timeutils.py`. PostgreSQL returns `DateTime(timezone=True)`
      columns as aware datetimes and SQLite returns them naive; mixing the two
      raises `TypeError`, which is how a page that works locally 500s in
      production.
- [x] **Deletion respects foreign keys** - deleting a login unlinks the
      household record, applications and certificates (which survive as
      official records) and removes the personal rows that cannot outlive it.
      An account that issued a certificate or filed a weekly report cannot be
      hard-deleted at all; the API says so and points at deactivation.
- [x] **Automated tests** - backend/tests/ covers auth boundaries, the full
      application lifecycle, document review, jurisdiction rules, OTP/session
      hardening, audit privacy, chat transparency, and the production-only
      failure modes above. Run with:
      ```
      cd backend
      pip install -r requirements-dev.txt
      pytest -v
      ```
      All tests must pass before you deploy any change.

## 2. Decisions YOU must make before going live (not optional)

### Database: managed Postgres or MySQL is mandatory

Render's filesystem is ephemeral - it's wiped on every redeploy and can be
wiped on a restart even without a redeploy. If you deploy with the default
SQLite fallback, every citizen, member, application, and certificate will
disappear the next time the service restarts.

You must provision a real Postgres database and set DATABASE_URL to its
connection string before putting real data in this app. Render's own managed
Postgres is the simplest option. The backend refuses to start in
production with SQLite configured.

### Uploaded documents & generated PDFs: same ephemeral-disk problem

Uploaded ID documents and generated certificate/approval PDFs are written
below `STORAGE_PATH`. On Render, that must be a mounted persistent disk (for
example `/var/data/janseva`) or those files vanish on redeploy. The backend
refuses production startup until `STORAGE_PATH` is set. `render.yaml`
provisions the disk for you.

For horizontal scaling, replace the mounted disk adapter with encrypted
object storage (such as a private S3 bucket) before adding a second backend
instance. Do not use public buckets for Aadhaar/identity documents.

Do not skip this decision. A citizen's uploaded Aadhaar card disappearing
after a routine redeploy is a real, embarrassing failure mode.

### Email delivery

Without real SMTP credentials, every OTP/notification email falls back to the
backend console in local development. Production startup refuses to proceed
until SMTP_HOST/SMTP_USER/SMTP_PASSWORD are set correctly.
See the README section on email OTP setup.

## 3. Required environment variables (backend .env on Render)

```
ENVIRONMENT=production
SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=<your real Postgres connection string - see section 2>
CORS_ORIGINS=https://your-actual-frontend-domain.com
ALLOWED_HOSTS=your-backend.onrender.com
STORAGE_PATH=/var/data/janseva
GROQ_API_KEY=<your real key, or leave blank to disable AI features>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<real sending address>
SMTP_PASSWORD=<real app password>
SMTP_FROM_NAME=JanSeva Connect
OTP_EXPIRY_MINUTES=10
```

Do not reuse the SECRET_KEY from local development or from this doc's
example - generate a fresh one for production and never commit it anywhere.

## 4a. Frontend on Vercel (optional alternative to Render Static Site)

See `frontend/DEPLOY-VERCEL.md` for the full walkthrough. In short:

1. Import the repo, set **Root Directory to `frontend`** (the repo is a
   monorepo; this is the setting people miss).
2. Set `VITE_API_URL=https://your-backend.onrender.com`. The build now
   **fails** rather than silently producing a bundle that calls localhost.
3. Set `CORS_ORIGINS` on the Render backend to the Vercel origin.

`frontend/vercel.json` supplies the SPA rewrite and security headers.
`frontend/public/_redirects` does the same job for Netlify and Render Static
Sites - Vercel ignores that file, hence both.

**The backend cannot run on Vercel.** It needs a persistent disk for uploaded
documents and generated PDFs, in-process rate-limit state, and background
tasks that outlive the response - none of which survive a serverless function.
Keep it on Render (or any host with a long-lived process and a mounted disk).

## 4b. Deployment steps (Render)

The repository includes `render.yaml`, a Render blueprint that provisions the
backend, the static frontend, the managed database, and the persistent disk
in one step. Point Render at the repo and choose "New Blueprint", then fill
in the values it marks as unset (they are all secrets or full URLs, which
deliberately are not committed).

To do it by hand instead:

Backend (Web Service):
1. New -> Web Service -> connect the repo, root directory `backend`
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
   (`--proxy-headers` matters: without it every request appears to come from
   Render's load balancer, so the per-IP rate limits throttle all users as one.)
4. Add all env vars from section 3, and mount a persistent disk at `STORAGE_PATH`
5. Health check path: `/api/health`
6. For a brand-new deployment, open the Render shell for this service and run:
   ```
   python seed.py         # creates the admin/staff accounts + sample schemes
   ```
   `seed.py` generates a strong random password for each account and prints it
   **once**. Save it immediately - it is not recoverable (use Forgot Password
   if it is lost). To choose your own instead, set `SEED_ADMIN_PASSWORD` /
   `SEED_STAFF_PASSWORD` before running; they must satisfy the same policy the
   API enforces.

   `migrate_db.py` is for local SQLite only. It refuses to run against a
   PostgreSQL `DATABASE_URL` rather than pretending to migrate it - a new
   Postgres deployment gets its schema from the app's first start.

Frontend (Static Site):
1. New -> Static Site -> same repo, root directory `frontend`
2. Build command: `npm ci && npm run build`
3. Publish directory: `dist`
4. Env var: `VITE_API_URL=https://your-backend.onrender.com`
5. Add a rewrite of `/*` to `/index.html`. The app is a single-page router,
   so without it every refresh on `/applications` or a pasted deep link
   returns the host's 404 page. (`frontend/public/_redirects` already covers
   hosts that read that file; `render.yaml` sets the equivalent route.)

## 5. Post-deploy smoke test (do this manually, once, after every deploy)

- [ ] Hit `/api/health` and confirm `{"status": "ok", "database": "ok"}` -
      a `503` with `"database": "unreachable"` means the app is up but the
      database is not
- [ ] Log in as admin with the seeded password
- [ ] Register a test citizen account end-to-end (should receive a real email now)
- [ ] Create a member, issue a certificate, download the PDF
- [ ] Apply to a scheme as the citizen, upload a document, approve it as admin
- [ ] Confirm the citizen received the approval email
- [ ] Send a chat message as the citizen, confirm it appears for staff
- [ ] Refresh the browser on `/applications` - it must load the app, not a 404

For local work, `backend/e2e_api_check.py` automates the equivalent of this
list against a running server (106 checks across citizen, staff, district
admin and superadmin). It is a development tool and expects the throwaway
configuration in `e2e_env.py`; never point it at production.

```
cd backend
python run_e2e_backend.py > e2e-backend.log 2>&1 &
python seed_e2e.py
python e2e_api_check.py
```

## 6. Known limitations (honest, not hidden)

- No automated migration framework (Alembic). `migrate_db.py` is a manual,
  hand-written script for specific SQLite column additions and explicitly
  refuses to run against PostgreSQL. A new Postgres deployment is fine
  (`create_all` builds the schema); changing the schema of an existing
  production database needs migration tooling you add yourself.
- Local disk storage for uploads/PDFs (see section 2) - functional for a
  single-instance deployment with a persistent disk, not yet built for
  horizontal scaling or object storage.
- In-memory rate limiting - correct for a single backend instance; if this
  is ever scaled to multiple instances behind a load balancer, the limiter
  needs a shared backend (Redis) or each instance enforces limits independently.
- The JWT is held in `localStorage`, which is the usual SPA trade-off: it
  survives a refresh, but any script running on the page could read it. The
  API sends a strict CSP and the UI never renders HTML from user or model
  input, so there is no known injection path today; moving to an httpOnly
  cookie would remove the class of risk entirely and is the natural next
  hardening step.
- Test coverage is smoke-level plus targeted regression tests for the
  failures listed in section 1 - not exhaustive coverage of every branch.
- **Repository history contains citizen documents.** 158 generated
  certificate PDFs and uploaded ID documents were committed before the
  `.gitignore` rules existed. They have been removed from tracking, so new
  commits are clean, but they remain in earlier commits. If this repository
  is or becomes public, purge them from history (`git filter-repo`) and
  treat those documents as disclosed.
