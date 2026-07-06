# SpaghettiHub (MoosicGenerator)

Taste-conditioned music generation web app. It reads your Spotify listening
taste, distills it into a **taste fingerprint** (genres, liked-track counts,
playlists), then lets you type a prompt and generate an original track shaped by
that taste.

**Flow:** Spotify OAuth (PKCE) → sync your library → build taste profile → type a
prompt → generate audio (MusicGen) → MP3.

Full product spec lives in [`Artifact.md`](./Artifact.md).

---

## Status

| Area | State |
|------|-------|
| Spotify PKCE auth | ✅ Done, works live against real Spotify |
| Library sync + taste profiling | ✅ Done (background job, rate-limit resilient) |
| Durable taste profile (cached) | ✅ Done |
| Angular frontend (login → sync → studio) | ✅ Done |
| OAuth tokens encrypted at rest | ✅ Done (Fernet) |
| **Music generation (MusicGen)** | ✅ Real inference — `transformers` MusicGen on CUDA, MP3 delivered to an in-app player |
| Celery worker / Redis | ⚙️ Wired for Docker, unused at runtime (sync + generation run in-process) |

**Tests:** 32 backend (`pytest`) + 53 frontend (`vitest`) passing.

---

## Architecture

```
frontend/   Angular 21 — standalone components, Signals, Tailwind v4 ("Overtone" theme)
backend/    FastAPI (Python 3.12) — Spotify auth, library sync, taste profiles
tests/      Backend pytest suite (in-memory SQLite)
design/     "Overtone" design system (dark navy, Playfair Display + Manrope)
```

### Backend (`backend/app`)

- **`main.py`** — app factory. Injects the OS trust store for TLS
  (`truststore`, needed behind TLS-intercepting proxies/AV), configures CORS from
  `FRONTEND_ORIGIN`, and runs **Alembic `upgrade head` on startup** so the schema
  is always current with a plain `uvicorn` launch.
- **`api/auth.py`** — real Spotify **PKCE** OAuth. `/auth/login` builds the
  authorize URL and stores the verifier; `/auth/callback` exchanges the code.
- **`api/library.py`** — `POST /library/sync` returns `202 + job_id` and runs the
  sync via FastAPI `BackgroundTasks` (not Celery). The worker looks up per-artist
  genres with throttling, exponential backoff on Spotify 429s, and incremental
  progress commits. `GET /library/sync/{job_id}` polls status; a fresh cached
  profile (< `PROFILE_TTL_DAYS`, default 14) is served without re-syncing.
- **`api/profile.py`** — `GET /library/profile` returns the stored fingerprint.
- **`api/generate.py`** — **stub.** In-memory job that progresses
  `pending → running → complete` deterministically and returns a fake MP3 URL.
  Real MusicGen inference + storage is the next phase.
- **`models/`** — 5 SQLAlchemy models: `oauth_state`, `user_session`,
  `artist_genre_cache`, `library_sync_job`, `taste_profile`.
- **`db/session.py`** — lazy engine (module imports without a live DB, so stubs
  and tests run offline). Runtime uses PostgreSQL; tests use in-memory SQLite.
- **`workers/celery_app.py`** — Celery app with a placeholder `ping` task, wired
  for the Docker `worker` service. Real generation tasks land later.
- **`alembic/`** — migrations are the single source of truth for the schema.

### Frontend (`frontend/src/app`)

- **Login** (Spotify only) → redirects to Spotify consent.
- **`/callback`** — reads `code`/`state` (sessionStorage CSRF check), calls the
  backend, starts a background `SyncStore` poll, and navigates straight to
  `/studio` without blocking.
- **Studio** — prompt screen: textarea, live genre chips, liked-track count, and
  a Generate button (hits the stub generate endpoint).
- **SyncDialog** — floating card showing background sync progress.
- API base URL comes from `src/environments/` (`http://localhost:8000` in dev).

---

## Running locally

**Prerequisites:** Python 3.12, Node 22+, PostgreSQL, and a Spotify developer app.

### 1. Configure

Copy the env template and fill in Spotify credentials:

```bash
cp .env.example .env
# set SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET, and DATABASE_URL
```

Register `http://127.0.0.1:4200/callback` as a Redirect URI in the Spotify
dashboard. **Browse the app at `http://127.0.0.1:4200`** (not `localhost`) — the
CSRF `state` check is per-origin and must match the redirect origin.

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
# GPU-only: torch is installed out-of-band from the CUDA index (the default
# PyPI wheel lacks kernels for recent GPUs, e.g. RTX 50-series / Blackwell):
pip install torch --index-url https://download.pytorch.org/whl/cu128
uvicorn app.main:app --reload    # auto-runs Alembic migrations on startup
```

**Music generation requires a CUDA GPU.** The service refuses to run MusicGen on
CPU (it would be unusably slow); jobs fail loud with a clear message if no GPU is
available. `ffmpeg` must be on PATH (used to transcode to MP3). The first
generation downloads `facebook/musicgen-small` (~1–2 GB) and warms slowly;
later generations reuse the warm model. Generated MP3s are written under
`backend/media/generations/` (git-ignored) and streamed to the browser via
`GET /generate/{job_id}/audio`.

### 3. Frontend

```bash
cd frontend
npm install
npm start                         # http://127.0.0.1:4200
```

### Tests

```bash
cd backend && pytest              # 32 tests
cd frontend && npm test           # 53 tests
```

---

## Docker (planned)

`docker-compose.yml` is present but not yet verified end-to-end. Before it works
cleanly the backend Dockerfile must also copy `alembic/` + `alembic.ini` (startup
migration needs them), and a frontend Dockerfile (nginx static + `/api` reverse
proxy) is still to be added. Redis/Celery can stay behind a compose profile until
real generation needs them.

---

## Configuration reference

Key settings (`backend/app/core/config.py`, sourced from repo-root `.env`):

| Var | Purpose |
|-----|---------|
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Spotify OAuth app credentials |
| `SPOTIFY_REDIRECT_URI` | Frontend `/callback` (default `http://127.0.0.1:4200/callback`) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Celery broker/backend (unused until real generation) |
| `FRONTEND_ORIGIN` | Comma-separated CORS origins |
| `PROFILE_TTL_DAYS` | How long a cached taste profile stays fresh (default 14) |
