# Deploying the frontend to Vercel

Only the **frontend** goes on Vercel. The FastAPI backend cannot run there —
see "Why not the backend" at the bottom — so it stays on Render (or any host
that gives you a persistent disk and a long-lived process).

## Setup

1. Vercel → **Add New → Project** → import this repository.
2. **Root Directory: `frontend`.** This is the one setting people miss. The
   repo is a monorepo; without it Vercel builds from the root, finds no
   `package.json`, and fails.
   Framework, build command, and output directory are already declared in
   `frontend/vercel.json`, so leave those as detected. Vercel reads
   `vercel.json` from the Root Directory and scopes the project to that
   subtree, so a config at the repo root would be ignored with this setting
   and silently take over without it. There is deliberately no longer one
   in this repo — do not reintroduce it.
3. Environment Variables → add, for **all** environments:

   | Name | Value |
   |---|---|
   | `VITE_API_URL` | `https://your-backend.onrender.com` |

   Include the scheme, and no trailing slash. This is baked in at build time,
   not read at runtime — changing it later requires a redeploy, not just a
   restart.
4. Deploy.

## Then point the backend at it

The backend refuses cross-origin requests it was not told about, so on the
Render service set:

```
CORS_ORIGINS=https://your-project.vercel.app
```

Add every origin you actually use, comma-separated. The value is split on
commas and each entry is `.strip()`ed (`app/core/config.py:68-75`), then passed
to Starlette's exact-membership test — so surrounding whitespace is forgiven,
but a trailing slash, a different case, or a missing scheme is fatal. There is
no wildcard and no regex arm: `app/main.py` never passes `allow_origin_regex`.

One trap costs more time than the rest combined: an `http://` entry does not
degrade into a CORS error. `app/main.py:40-53` refuses a production boot and
calls `sys.exit(1)`, which presents as a total backend outage rather than a
configuration mistake. Keep localhost origins out of the production value.

**Preview deployments.** Per-commit URLs carry a random hash and can never be
pre-listed. The per-branch URL `<project>-git-<branch>-<scope>.vercel.app` is
stable and can be added literally. Preview builds also need `VITE_API_URL`
ticked for the Preview environment, or `vite.config.js` fails the build
outright — by design.

Two things that do **not** need attention: auth is a Bearer token in
localStorage (`src/api/client.js`), not a cookie, so `allow_credentials` and
SameSite are irrelevant to the new cross-site pairing; and nothing server-side
builds an absolute frontend URL — there is no `FRONTEND_URL`, and the outgoing
emails carry codes rather than links, so moving the frontend breaks no email.

`ALLOWED_HOSTS` on the backend is about the **backend's own** hostname, not
the frontend's — set it to `your-backend.onrender.com`.

## Client-side routing

`vercel.json` rewrites everything that is not a real asset to `/index.html`.
Without it, a refresh on `/applications` or a pasted deep link returns
Vercel's 404 page, because those routes exist only in the browser's router.

`frontend/public/_redirects` does the same job for Netlify and Render Static
Sites. Vercel ignores that file — hence the separate config. Both are kept so
the frontend deploys correctly on any of the three.

## Why not the backend

Vercel runs Python as short-lived serverless functions. Four things in this
application are incompatible with that model:

- **Uploaded documents and generated PDFs need a real filesystem.** Vercel's
  is read-only apart from `/tmp`, which is discarded between invocations. A
  citizen's uploaded Aadhaar card would vanish immediately.
- **Rate limiting is in-process** (`app/core/rate_limit.py`). Every function
  instance would keep its own counters, so the login/OTP limits stop meaning
  anything once more than one instance is warm.
- **`Base.metadata.create_all()` runs at import.** On serverless that is once
  per cold start, against your production database.
- **Email is sent via FastAPI `BackgroundTasks`**, which run after the
  response is returned. A serverless function can be frozen at that point,
  silently dropping OTP and notification emails.

Making it serverless-ready means object storage (S3), Redis-backed rate
limiting, a migration step outside the request path, and a real queue for
email. That is a genuine re-architecture, not a config change.
