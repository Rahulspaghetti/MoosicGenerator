# Phase 3 — MusicGen generation + audio delivery

**Date:** 2026-07-05
**Status:** Approved (design)

## Goal

Replace the `/generate` stub with real text-to-music generation using MusicGen,
and deliver the resulting audio to the browser as a playable MP3. Pressing
**Generate** in the Studio must produce an actual track the user can play.

## Decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime | HuggingFace `transformers` MusicGen | Runs on modern torch (cu128) that supports the RTX 5060 (Blackwell / sm_120); Meta `audiocraft` pins torch 2.1.0 with no Blackwell kernels. |
| Model | `facebook/musicgen-small` (300M) | Fits 8 GB VRAM comfortably; fast iteration. Swappable via config. |
| Clip length | ~30 seconds | `max_new_tokens = duration_s * 50`. |
| Device | **CUDA only — NO CPU fallback** | If `torch.cuda.is_available()` is False, fail loud (job → failed). Never silently run the 300M model on CPU. |
| Execution | FastAPI `BackgroundTasks` + DB-backed job | Redis is down; this mirrors the proven `LibrarySyncJob` pattern. |
| GPU concurrency | Single module-level `threading.Lock` | Serialize GPU access so two jobs can't OOM 8 GB. |

## Architecture

### Data flow

```
[Studio: prompt] --POST /generate--> 202 {job_id, status=pending}
        |
        v  background worker (own DB session), one at a time (GPU lock)
   status=running
   MusicGen inference (CUDA) -> float32 mono @ 32kHz
        -> ffmpeg transcode (raw PCM via stdin) -> MP3 on disk
        -> backend/media/generations/{job_id}.mp3
   status=complete, audio_path set
        |
[Studio polls GET /generate/{job_id} every 2s]  -> status/progress/step/url
        |  on complete:
        v
   GET /generate/{job_id}/audio  -- FileResponse(audio/mpeg, Range) -->
        <audio controls src="…/audio">  ▶
```

### Components

**`app/models/generation_job.py` — `GenerationJob` (table `generation_jobs`)**
- `job_id: str` (PK, `job_{uuid.hex[:12]}` — keep existing id format)
- `session_id: str`
- `prompt: str` (Text)
- `status: str` — `pending | running | complete | failed`
- `progress: float` (0.0–1.0, default 0)
- `step: str | None` — human-readable stage
- `audio_path: str | None` — path relative to `MEDIA_ROOT`
- `error: str | None`
- `created_at: datetime`

Registered in `app/models/__init__.py`.

**`app/services/musicgen.py`** — lazy warm singleton.
- `_require_cuda()`: raises `RuntimeError("CUDA GPU required; refusing to run MusicGen on CPU.")` if `torch.cuda.is_available()` is False.
- `_load()` (once): `_require_cuda()`, then `AutoProcessor.from_pretrained(MODEL)` +
  `MusicgenForConditionalGeneration.from_pretrained(MODEL).to("cuda")`. Cached in
  a module global; reused across jobs.
- `generate(prompt: str, duration_s: int) -> tuple[np.ndarray, int]`:
  processor(text=[prompt]) → `model.generate(max_new_tokens=duration_s*50)` →
  return `(mono float32 waveform, 32000)`. Wrapped in the module `threading.Lock`.

**`app/services/audio.py`**
- `pcm_to_mp3(samples: np.ndarray, sample_rate: int, out_path: Path) -> None`:
  spawns `ffmpeg -f f32le -ar {sr} -ac 1 -i pipe:0 -codec:a libmp3lame -q:a 4 -y out.mp3`,
  writes `samples.astype("<f4").tobytes()` to stdin. Raises on non-zero exit
  (e.g. ffmpeg missing) with captured stderr.

**`app/api/generate.py`** (full rewrite — remove in-memory `_JOBS`)
- `POST /generate` (202): validate session exists (404 if not), create
  `GenerationJob` (pending), `background_tasks.add_task(_run_generation, job_id)`,
  return `GenerateResponse{job_id, status="pending"}`.
- `_run_generation(job_id)`: own session via `get_session_factory()`. Steps update
  `status/step/progress`: `running`→"Warming model" (0.1)→"Composing" (0.4)→
  "Rendering audio" (0.85)→`complete` (1.0) with `audio_path`. Any exception →
  `status="failed"`, `error=str(exc)`, `progress` frozen. CUDA-missing surfaces
  here as a failed job with the explicit message.
- `GET /generate/{job_id}` → `GenerateStatusResponse`. `url = "/generate/{job_id}/audio"`
  only when `status=="complete"`. 404 if job unknown.
- `GET /generate/{job_id}/audio` → `FileResponse(path, media_type="audio/mpeg")`.
  404 if job/file missing. Starlette FileResponse sets `Accept-Ranges` and serves
  HTTP Range requests, enabling seek/stream in `<audio>`.

**`app/core/config.py`** — new settings:
- `MUSICGEN_MODEL: str = "facebook/musicgen-small"`
- `GENERATION_DURATION_S: int = 30`
- `MEDIA_ROOT: str = "<backend>/media"` (absolute, resolved like `_ENV_FILE`)

`app/main.py` lifespan: `Path(MEDIA_ROOT, "generations").mkdir(parents=True, exist_ok=True)` after migrations.

**Schemas** — `GenerateRequest` unchanged; `enhance_lyrics` / `reference_sample_ids`
remain accepted-but-ignored (prompt-only conditioning this phase).
`GenerateResponse` / `GenerateStatusResponse` unchanged.

**Alembic** — one migration creating `generation_jobs`.

### Frontend

**`core/api/api.ts`** — no change (`generate`, `getGenerateStatus` already exist).

**`features/studio/studio.ts`**
- After `generate()` returns `job_id`, start polling `getGenerateStatus(job_id)`
  with `timer(0, 2000).pipe(switchMap(...), takeWhile(notTerminal, inclusive))`.
- Signals: `genStep`, `genProgress`, `genStatus`, `audioUrl` (computed:
  `environment.apiBaseUrl + status.url` when complete).
- Cancel any in-flight poll when a new generation starts; clean up on destroy.

**`features/studio/studio.html`**
- Replace the "player arrives in the next phase" block with:
  - while running: `step` text + progress (`aria-live="polite"`).
  - on failed: `role="alert"` error.
  - on complete: `<audio controls [src]="audioUrl()">` + the prompt used.

## Error handling

| Failure | Behavior |
|---------|----------|
| No CUDA GPU | Job `failed`, error "CUDA GPU required; refusing to run MusicGen on CPU." |
| CUDA OOM / model load error | Job `failed`, error = exception string. |
| ffmpeg missing / non-zero | Job `failed`, error includes ffmpeg stderr. |
| Unknown `job_id` | 404 on status and audio endpoints. |
| Audio file missing though complete | 404 on `/audio`. |
| Concurrent generations | Serialized by GPU lock; each still tracked as its own job. |

## Testing

**Backend** (`tests/test_generate.py`, rewritten)
- Patch `app.services.musicgen.generate` → returns `(np.zeros(32000*1, np.float32), 32000)`
  so the real model never loads; **real ffmpeg** transcodes the tiny buffer (ffmpeg
  is on PATH). BackgroundTasks run synchronously under `TestClient`.
- Cases: happy path (POST→job, GET status `complete`, `url` set, MP3 file exists);
  `GET /generate/{id}/audio` → 200 `audio/mpeg`, non-empty body; unknown job → 404
  (status + audio); failed path (patch `generate` to raise → job `failed`, error set);
  unknown session → 404 on POST.
- A separate test patches `torch.cuda.is_available` → False and asserts the job fails
  with the no-CPU message (without importing/loading the model).

**Frontend** (`features/studio/studio.spec.ts`, extended)
- Mocked `Api`: `generate` → `{job_id}`; `getGenerateStatus` → running then complete.
- Fake timers drive the poll; assert step/progress render, then `<audio>` appears with
  the composed `src`. Failed-status branch renders the alert.
- Existing a11y spec still passes.

## Install / ops notes (not code)

- Add `transformers` (and its runtime deps) to `backend/requirements.txt` — normal PyPI.
- `torch` is installed **out-of-band** from the cu128 index, not pinned in
  `requirements.txt` (the default PyPI torch wheel lacks Blackwell kernels):
  `pip install torch --index-url https://download.pytorch.org/whl/cu128`. This
  command is documented in the README.
- First real generation downloads `facebook/musicgen-small` (~1–2 GB) and warms slowly;
  later generations reuse the warm model.
- `backend/media/` is already git-ignored.

## Out of scope (YAGNI this phase)

- Lyrics conditioning / `enhance_lyrics`.
- Reference-audio melody conditioning / `reference_sample_ids`.
- Celery/Redis migration (stays on BackgroundTasks).
- Persisting generations to the taste profile or a history list.
- Auth/ownership checks on `/audio` (any session can fetch any job's audio by id).
