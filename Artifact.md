# Building a Personalized, Taste-Conditioned Music Generation App: A Professor-Level Technical Plan (July 2026)

## TL;DR
- **Build in four phases with a three-person team, and treat the Python backend as the brain** that orchestrates a linear pipeline: Spotify OAuth → statistical/embedding taste profile → profile-to-text prompt → MusicGen → MP3. Everything else (UI, tests) plugs into contracts the backend exposes.
- **The single most important 2026 reality check:** Spotify's `audio-features` and `audio-analysis` endpoints have returned 403 for all new apps since November 27, 2024, and there is still no official replacement 18 months later. You therefore cannot get danceability/energy/valence/tempo directly from Spotify for a newly-registered app. Build the taste profile primarily from **genre/artist metadata + Liked Songs** (still available under `user-library-read`), and optionally enrich with a **third-party audio-feature API (ReccoBeats)** or **self-computed Essentia features**.
- **Use an existing Hugging Face model — Meta's MusicGen (`facebook/musicgen-small/medium/large`)** — and run generation as an **asynchronous background job** (never a synchronous HTTP request), on a serverless GPU (Modal/Replicate) or a local GPU. For a portfolio demo, `musicgen-small` is the pragmatic default.

---

## Key Findings

### 1. Spotify API — verified current state (mid-2026)
- **The November 2024 lockdown.** As TechCrunch reported (Nov 27, 2024): "Spotify will no longer allow developers building third-party apps with its Web API to access several features … such as song and artist recommendations." The affected endpoints — `audio-features`, `audio-analysis`, `recommendations`, related-artists, and featured-playlists — began returning **403 for new apps the same day**. Only apps that already held (or had a pending) quota extension before that date are grandfathered.
- **Still no replacement.** As FreqBlog summarized in 2026: "Eighteen months later, there is still no official replacement … Apps that had a quota extension in flight on November 27, 2024 are still live. Everyone else gets 403." There is no waitlist and no public statement that access will return.
- **The February 2026 "Dev Mode" tightening** (per Spotify's own migration guide) made the rest of the API harder for small/new apps:
  - New Development Mode apps are capped at **5 users** and **1 Client ID**, and the **app owner must have an active Spotify Premium subscription**.
  - Batch fetch endpoints removed (`GET /tracks`, `/artists`, `/albums` → must fetch individually).
  - `popularity` was **removed** from Track and Artist objects; `available_markets` removed; `GET /artists/{id}/top-tracks` and browse endpoints removed.
  - `GET /search` `limit` max dropped from 50 → **10** (default 5).
  - `GET /me/tracks` (**Liked Songs**) **remains available** with the `user-library-read` scope — this is the backbone of your ingestion.
- **OAuth:** You must use **Authorization Code with PKCE**. The Implicit Grant flow was removed on **November 27, 2025**, along with HTTP redirect URIs and `localhost` aliases (you may still use `http://127.0.0.1`, but production requires HTTPS).
- **Python library:** The maintained **spotipy-dev fork of Spotipy** (v2.25.1, released Feb 27, 2025) is the standard choice; it supports PKCE via the `SpotifyPKCE` auth manager and automatic token refresh. A recent release also tightened token-cache file permissions to `600` (CVE-2025-27154).
- **Audio-feature alternatives:** **ReccoBeats** (free, returns Spotify-shaped `danceability`, `energy`, `valence`, `acousticness`, `tempo`, etc., accepts Spotify IDs, batch endpoint but rate-limited — practitioners throttle to ~5 IDs/request with a ≥0.5s delay to avoid 429s); **Essentia** self-computation from 30-second preview clips; and the **AcousticBrainz** public dump (7.5M tracks, frozen at July 2022).

### 2. Taste profile — statistical + embedding approach
- Aggregate per-track features into a **user taste vector** (means, standard deviations, and distributions), **cluster** with k-means or a Gaussian Mixture Model to find "taste clusters," **embed** genre tags with sentence-transformers, and **reduce** to 2-D with PCA/UMAP for a visualization the UI can render.
- The **critical bridge** is *profile-to-prompt translation*: converting numeric feature ranges + dominant genres/eras into MusicGen's natural-language prompt vocabulary (e.g., high energy + high tempo + "electronic" → *"energetic EDM with driving synths and a four-on-the-floor beat, ~128 BPM"*).

### 3. MusicGen — architecture & practical facts
- MusicGen is (per the `facebook/musicgen-large` model card) "a single stage auto-regressive Transformer model trained over a 32kHz EnCodec tokenizer with 4 codebooks sampled at 50 Hz … By introducing a small delay between the codebooks, we show we can predict them in parallel, thus having only 50 auto-regressive steps per second of audio." Text conditioning uses a **frozen T5 text encoder** via cross-attention; training uses **cross-entropy** loss and **classifier-free guidance**.
- **Training data:** Per the MusicGen paper (Copet et al., *Simple and Controllable Music Generation*, arXiv:2306.05284, §3.2): "We use 20K hours of licensed music to train MUSICGEN. Specifically, we rely on an internal dataset of 10K high-quality music tracks, and on the ShutterStock and Pond5 music data collections with respectively 25K and 365K instrument-only music tracks."
- **Sizes:** Per the Hugging Face model card, "The model comes in different sizes: 300M, 1.5B and 3.3B parameters" — `musicgen-small` (300M), `musicgen-medium` (1.5B), `musicgen-large` (3.3B; Replicate's page labels it "3.5 billion," a minor inconsistency — 3.3B is authoritative).
- **Hardware:** Meta's `audiocraft/docs/MUSICGEN.md` states: "AudioCraft requires a GPU with at least 16 GB of memory for running inference with the medium-sized models (~1.5B parameters)." Benchmarks: on a Colab **T4**, Pragnakalp Techlabs reports "~9 minutes to generate 10 seconds of audio using CPU whereas using GPU(T4) it took just 35 seconds" (small model). Replicate's A100 (80GB) deployment reports typical predictions "within 72 seconds." Output is **capped at 30 seconds** (1503 tokens). Note: generation is partly single-core-CPU-bound, so an A100 is often **not** dramatically faster than a 3090 for single samples.

### 4. Backend architecture
- **FastAPI** (async, typed via Pydantic) is the right framework. A 30–120 second generation must run as a **background job** (Celery + Redis, or the async-native ARQ), with a **status-polling** endpoint — synchronous HTTP will time out and block the event loop. Model hosting options: **local GPU**, **Modal** (per-second serverless billing, scale-to-zero), or **Replicate** (acquired by Cloudflare in early 2026; convenient but cold starts and per-second billing). Store taste profiles in **SQLite → Postgres**; store MP3s on **local filesystem → S3**.

---

## Details (organized by phase, professor-style)

### Phase 0 — Foundations, secrets, and interface contracts (all three roles)
Before writing features, lock down the skeleton so the three agents can work in parallel without blocking each other.

- **Repo + environment:** A monorepo with `/frontend`, `/backend`, `/tests`. Use **Docker Compose** to run four services locally: `api` (FastAPI/uvicorn), `worker` (Celery/ARQ), `redis` (broker + result store), `db` (Postgres).
- **Secrets management (concept + practice):** Never commit credentials. Keep `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, `RECCOBEATS_API_KEY`, `HF_TOKEN`, and any cloud-GPU token in a `.env` file that is git-ignored, loaded via **pydantic-settings** (`BaseSettings`). In production use the platform's secret store (Modal Secrets, Fly.io secrets, AWS Secrets Manager). The Spotify **client secret must live only server-side** — PKCE means the browser never sees it.
- **Interface contracts (the glue):** The backend publishes an **OpenAPI schema** (FastAPI generates this automatically at `/docs`). This document is the contract the UI developer codes against and the SDET writes tests against. Agree on it in Phase 0 so nobody waits on anyone.

**The contract, at a glance:**

| Method | Endpoint | Purpose | Owner of consumer |
|---|---|---|---|
| `GET` | `/auth/login` | Returns Spotify authorize URL (PKCE challenge) | UI |
| `GET` | `/auth/callback` | Exchanges code → tokens, creates session | UI |
| `POST` | `/library/sync` | Ingests Liked Songs + artist genres | UI (button) |
| `POST` | `/profile/build` | Computes taste profile from ingested data | UI |
| `GET` | `/profile` | Returns profile summary + 2-D cluster viz data | UI |
| `POST` | `/generate` | Accepts text prompt, returns `job_id` | UI |
| `GET` | `/generate/{job_id}` | Poll job status; returns MP3 URL when done | UI |

---

### Phase 1 — Spotify OAuth + data ingestion (Backend + UI)

**Professor's explanation of OAuth 2.0 Authorization Code with PKCE.** OAuth exists so your app can act *on behalf of* a user without ever seeing their password. PKCE ("pixie," Proof Key for Code Exchange) hardens the flow against interception attacks for clients that can't perfectly hide a secret. The dance:

1. **Generate a `code_verifier`** — a high-entropy random string 43–128 characters long.
2. **Derive a `code_challenge`** = `BASE64URL-ENCODE(SHA256(code_verifier))`. You send the *challenge* now and prove you know the *verifier* later — an eavesdropper who steals the challenge cannot reverse the SHA-256 to get the verifier.
3. **Redirect to `/authorize`** with `client_id`, `redirect_uri`, `response_type=code`, `scope=user-library-read`, `code_challenge`, `code_challenge_method=S256`, and a random `state` (CSRF protection).
4. **User logs in and consents.** Spotify redirects back to your `redirect_uri` with `?code=...&state=...`.
5. **Exchange the code** at `POST https://accounts.spotify.com/api/token`, sending the `code` *and* the original `code_verifier`. Spotify hashes the verifier, compares to the stored challenge, and — if they match — returns an **access token** (short-lived, ~1 hour) and a **refresh token** (long-lived).
6. **Refresh** transparently: when the access token nears expiry, POST the refresh token to get a new access token. Spotipy's `SpotifyPKCE`/`SpotifyOAuth` managers handle caching and refresh for you.

**Scopes:** For Liked Songs you only need **`user-library-read`**. Request the minimum — users are more likely to consent, and it's good security hygiene.

**Ingestion endpoints and pagination.** `GET /me/tracks` returns Liked Songs **50 at a time** with `limit`/`offset` (or the `next` cursor). Pseudocode with Spotipy:

```python
def sync_liked_songs(sp):  # sp = authenticated spotipy.Spotify
    tracks, results = [], sp.current_user_saved_tracks(limit=50)
    while results:
        tracks.extend(results["items"])
        results = sp.next(results) if results["next"] else None
    return tracks
```

Then collect the **artist IDs**, fetch `GET /artists/{id}` for **genres** (Spotify attaches genre tags to *artists*, not tracks), dedupe, and cache. Because batch `GET /artists` was removed in Feb 2026 for dev-mode apps, fetch individually and **cache aggressively** (store artist→genres in your DB so re-syncs are cheap). Handle **HTTP 429** rate limits with exponential backoff — a real reported failure mode is looping over hundreds of tracks and getting locked out for hours with no `Retry-After` header.

**Audio features (the workaround).** Since Spotify's own endpoint is dead for you, after ingesting track IDs, call **ReccoBeats** (`GET https://api.reccobeats.com/v1/audio-features?ids=...`) in **small batches (~5 IDs) with throttling** to retrieve Spotify-shaped `energy`, `valence`, `danceability`, `acousticness`, `tempo`, etc. Design the backend so audio features are an **optional enrichment layer** — if ReccoBeats is unavailable, the profile still works on genres/artists/popularity/era alone.

**Who owns what in Phase 1:**
- **UI dev:** "Connect Spotify" button → hits `/auth/login`, handles the redirect, shows a "syncing…" state, then a library summary. (User provides the HTML designs.)
- **Backend dev:** All four auth/ingestion endpoints, token storage, pagination, ReccoBeats client, caching.
- **SDET:** Records **vcrpy cassettes** of real Spotify + ReccoBeats responses so integration tests never hit the network; writes tests for pagination edge cases (empty library, exactly 50 tracks, 51 tracks) and 429 backoff.

---

### Phase 2 — Taste profile engine (Backend — the math-heavy phase)

This is where the "aspiring FDE" demonstrates ML fundamentals. Explain each concept with intuition.

**Step 1 — Feature vectors and vector spaces.** Represent each track as a point in a vector space. The numeric audio features (energy, valence, danceability, acousticness, tempo, plus derived features like release-year and popularity) form a vector like `[0.84, 0.43, 0.59, 0.002, 118, 2019, 71]`. A *vector space* just means "every song is a point, and geometry (distance, direction) now encodes musical meaning."

**Step 2 — Normalization (z-scores).** Tempo (~60–200) dwarfs energy (0–1) numerically, so raw Euclidean distance would be dominated by tempo. Standardize each feature: `z = (x − mean) / std`. Now every dimension contributes fairly. Use `scikit-learn`'s `StandardScaler`.

**Step 3 — Aggregation into a profile.** The simplest profile is the **centroid** (mean vector) of all liked songs, plus the **standard deviation** per feature (how eclectic vs. focused the taste is). But a single mean hides multi-modal taste (someone who loves both ambient and metal averages to a bland "mid" that represents neither).

**Step 4 — Clustering to find "taste clusters."**
- **k-means:** Partition songs into `k` groups by iteratively assigning each point to the nearest centroid and recomputing centroids. Choose `k` with the **silhouette score** (how well-separated clusters are) or the **elbow method**. Each resulting centroid is a "taste cluster" — e.g., cluster A = high-energy electronic, cluster B = mellow acoustic.
- **Gaussian Mixture Model (GMM):** A "soft" version — each song gets a *probability* of belonging to each cluster, which better models overlapping tastes. Use `sklearn.mixture.GaussianMixture`.
- Both let you generate music that reflects a *specific facet* of the user's taste rather than a muddy average.

**Step 5 — Genre embeddings.** Genres are text, not numbers. Two options:
- **TF-IDF:** Treat each user's genre-tag collection as a document; TF-IDF weights rare-but-characteristic genres (e.g., "witch house") above ubiquitous ones ("pop"). Simple, interpretable, no model download.
- **sentence-transformers embeddings:** Encode each genre string (or an artist description) into a dense vector with a model like `all-MiniLM-L6-v2`. Now "deep house" and "tech house" land *near each other* in vector space even though the strings differ — semantic similarity the TF-IDF approach misses. Cluster these embeddings (the sentence-transformers library ships k-means and agglomerative clustering examples) to derive representative **"taste descriptors."**

**Step 6 — Cosine similarity.** To compare two taste vectors (or find the genre nearest a cluster centroid), use cosine similarity = `(A·B)/(‖A‖‖B‖)` — it measures the *angle* between vectors, ignoring magnitude. This is the standard similarity metric for embeddings.

**Step 7 — Dimensionality reduction for visualization.** Embeddings live in hundreds of dimensions; humans see two. **PCA** (linear, fast, preserves global variance) or **UMAP** (non-linear, preserves local neighborhood structure, prettier clusters) projects to 2-D so the UI can plot the user's "taste map." This is visualization only — cluster on the full-dimensional data, then reduce for display.

**Step 8 — The critical bridge: profile → text prompt.** MusicGen speaks natural language, so you must translate numbers into words. Use a rules/template layer:

```python
def profile_to_prompt(cluster):
    parts = []
    if cluster["energy"] > 0.66:   parts.append("energetic")
    elif cluster["energy"] < 0.33: parts.append("mellow, relaxed")
    if cluster["valence"] > 0.6:   parts.append("upbeat and bright")
    elif cluster["valence"] < 0.4: parts.append("melancholic")
    parts.append(f"{top_genre(cluster)}")           # e.g. "electronic / house"
    parts.append(f"around {int(cluster['tempo'])} BPM")
    if cluster["acousticness"] > 0.6: parts.append("with acoustic instruments")
    else: parts.append("with driving synths and electronic drums")
    return ", ".join(parts)
# → "energetic, upbeat and bright, electronic / house, around 128 BPM, with driving synths"
```

You then concatenate the user's free-text prompt ("something for a late-night drive") with this taste-derived descriptor to condition generation. An advanced variant uses an LLM to fuse them into fluent prose, but the rules-based version is transparent, testable, and interview-defensible.

---

### Phase 3 — Generation pipeline (Backend + ML)

**Loading and running MusicGen (Hugging Face transformers):**

```python
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import scipy, torch

processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
model.to("cuda")  # or "cpu" (very slow)

inputs = processor(text=[prompt], padding=True, return_tensors="pt").to("cuda")
audio = model.generate(**inputs, do_sample=True, max_new_tokens=512)  # ~10s of audio
sr = model.config.audio_encoder.sampling_rate  # 32000 Hz
scipy.io.wavfile.write("out.wav", rate=sr, data=audio[0, 0].cpu().numpy())
```

**Audio output handling.** MusicGen returns a torch tensor at **32 kHz**. Write it to WAV with `scipy.io.wavfile` (or `torchaudio.save`), then transcode to **MP3** with **pydub** (which shells out to **ffmpeg**):

```python
from pydub import AudioSegment
AudioSegment.from_wav("out.wav").export("out.mp3", format="mp3", bitrate="192k")
```

Ensure `ffmpeg` is installed in the Docker image — newer `torchaudio`/`pydub` both depend on it.

**HOW MUSICGEN WAS TRAINED — professor-level explanation with a small worked example (explicitly requested).**

MusicGen has three components, two of them **frozen** (not trained) and one **trained**:

1. **EnCodec (the audio tokenizer).** Raw audio is a firehose — 32,000 float samples per second. You cannot run a transformer over that directly. EnCodec is a convolutional autoencoder that **compresses audio into discrete tokens**. Its trick is **Residual Vector Quantization (RVQ)**:
   - Plain **Vector Quantization** rounds a continuous vector to the nearest entry ("centroid") in a learned **codebook**. High fidelity would need an impossibly huge codebook.
   - **RVQ** uses a *stack* of small codebooks. Quantize with codebook 1; take the **residual** (what codebook 1 got wrong); quantize *that* with codebook 2; take the new residual; and so on. Formally, for a frame `x`: pick `i₁ = argmin‖x − c₁ₖ‖`, then `r₁ = x − c₁,ᵢ₁`, then `i₂ = argmin‖r₁ − c₂ₖ‖`, etc. MusicGen uses **4 codebooks, each of size 2048**, producing **4 tokens per 20 ms frame (50 Hz)**. Codebook 1 captures coarse structure; later codebooks add fine detail. This is like JPEG quality layers for audio.

2. **T5 text encoder (the conditioning).** The text description is passed through a **frozen T5 encoder**, producing a sequence of hidden-state vectors. Frozen = its weights don't change during MusicGen training; it's a pre-trained "language understander" borrowed off the shelf.

3. **The transformer decoder (the only part actually trained).** An autoregressive Transformer LM that predicts the next audio tokens, **conditioned on the T5 text embeddings via cross-attention**.

**The delay pattern (why it's fast).** Naively, predicting 4 codebooks per frame means either flattening them into a 4× longer sequence (slow, quadratic attention cost) or predicting them independently (loses inter-codebook dependencies). MusicGen's **delay pattern** offsets each codebook by one step so the model predicts all 4 codebooks in parallel at each timestep while still conditioning later codebooks on earlier ones — giving "only 50 auto-regressive steps per second of audio."

**Small concrete worked example — one training pair flowing through training:**

> **Training pair:** a 5-second audio clip + its text caption *"upbeat acoustic folk with fingerpicked guitar."*
>
> 1. **Text → embedding:** T5 encodes the caption → a sequence of hidden vectors `z_text` (frozen; no gradient).
> 2. **Audio → tokens:** EnCodec encodes the 5s clip. At 50 Hz × 5s = 250 frames × 4 codebooks = **1000 discrete tokens** (each an integer in [0, 2047]). These are the **ground-truth targets**.
> 3. **Delay-pattern arrangement:** the 4 codebook streams are offset by the delay pattern so they can be predicted in parallel.
> 4. **Forward pass:** at each step the decoder, attending to `z_text` via cross-attention and to previously-generated tokens via causal self-attention, outputs a **probability distribution over the 2048 codebook entries** for each of the 4 codebooks — i.e., "given the text and the music so far, what's the next token?"
> 5. **Loss:** compare the predicted distributions to the true EnCodec tokens with **cross-entropy loss**. Cross-entropy is high when the model puts low probability on the correct token, low when it's confident and right. Backprop updates *only the decoder* (T5 and EnCodec stay frozen).
> 6. **Repeat** over 20K hours of clips. The decoder learns "captions like *acoustic folk* ⇒ token patterns that EnCodec decodes into fingerpicked-guitar audio."
>
> **At inference**, you reverse it: text → T5 → decoder autoregressively samples tokens → EnCodec **decoder** turns tokens back into a 32 kHz waveform. **Classifier-free guidance** (training 10% of the time with the text dropped, then at inference extrapolating between the conditioned and unconditioned predictions with a guidance scale γ) sharpens how strongly the output obeys the prompt.

**Alternatives worth knowing (2025–2026):**
- **Stable Audio Open** (Stability AI, 2024) — 1.3B latent-diffusion model, 44.1 kHz stereo, CC-trained, runs on consumer GPUs; **Stable Audio Open 1.5** and, per a May 2026 announcement, **Stable Audio 3** (open-weight small/medium variants) push quality and licensing transparency further.
- **YuE** (M-A-P, Apache 2.0) and **ACE-Step** (3.5B, Apache 2.0, diffusion, runs in ~8 GB VRAM) — strong 2025/2026 open options; ACE-Step's diffusion approach iterates faster than autoregressive MusicGen.
- **AudioCraft ecosystem** — Meta's umbrella library (MusicGen, EnCodec, AudioGen, MAGNeT).
- MusicGen remains the best-documented, most-tutorialed starting point, and CC-BY-NC (non-commercial) — fine for a portfolio project.

**Fine-tuning (advanced extension, not core).** You can **LoRA-fine-tune** MusicGen on a small custom dataset by training only low-rank adapters on the decoder's query/value projection layers while keeping T5 and EnCodec frozen — published work fine-tunes ~352M of a 1.5B model in ~2 days on 4×RTX-3090. Mention it as a "future work" bullet; do not attempt it for v1.

**Who owns what in Phase 3:**
- **Backend/ML dev:** model loading, the generation worker, WAV→MP3, storage, `profile_to_prompt`.
- **SDET:** generation **evals** (below).

---

### Phase 4 — Backend architecture deep-dive & integration (Backend + SDET)

**Why synchronous HTTP fails.** A MusicGen call takes ~35 seconds (T4) to 1–2 minutes. If your FastAPI route runs generation inline, the HTTP connection is held open the whole time — browsers/proxies time out (~30–60s), the server's worker is blocked, and one request can starve the whole app. **Generation must be decoupled from the request.**

**Background-job patterns (choose per complexity):**
- **FastAPI `BackgroundTasks`** — runs *in the same process* after the response returns. Fine for fire-and-forget (logging, emails); **wrong** for GPU inference — no status tracking, no retries, lost if the server restarts, and it competes with the event loop.
- **Celery + Redis** (recommended baseline) — a separate **worker process** pulls jobs from a **Redis** broker; results/status stored in Redis. Survives API restarts, supports **retries**, and lets you **scale GPU workers independently** from the web tier. The canonical choice for "AI workload longer than a few seconds."
- **ARQ** — async-native, lighter than Celery, pairs naturally with FastAPI's `async def`; a fine modern alternative if you prefer asyncio end-to-end.

**Job lifecycle:** `POST /generate` enqueues a task and immediately returns `{"job_id": ...}`. The worker sets status `pending → running → complete/failed` in Redis/DB and writes the MP3. The UI **polls** `GET /generate/{job_id}` until it returns `{"status":"complete","url": "..."}`. (Server-Sent Events/websockets are a nicer UX upgrade later.)

**Where to run the model — cost/latency trade-offs (2026):**

| Option | Latency | Cost model | Best for |
|---|---|---|---|
| **Local GPU** (≥16GB for medium; small runs on 8GB) | No cold start; instant | Fixed hardware cost | Dev, demos, learning |
| **Modal** | Cold start seconds; scale-to-zero | **Per-second** serverless (e.g., H100 ≈ $0.0011/s); minimal idle billing | Bursty, hobby-scale inference — usually cleanest economics |
| **Replicate** | Cold starts on unpopular models | Per-second hardware **or** per-output; **public** models bill only active time | Fast prototyping; convenience over lowest cost (acquired by Cloudflare, early 2026) |
| **HF Inference Endpoints** | Dedicated; you pick GPU | Per-hour dedicated | Steady traffic |

For a portfolio project: develop against a **local GPU or free Colab T4**, deploy the demo on **Modal** (scale-to-zero means you pay ~nothing when idle) running **`musicgen-small`**.

**Storage & caching:**
- **Taste profiles:** start with **SQLite** (zero-config, file-based), migrate to **Postgres** when you add multi-user/concurrency. Store the raw feature vectors, cluster centroids, and the derived prompt.
- **Generated MP3s:** **local filesystem** for dev; **S3** (or S3-compatible) for production, serving via presigned URLs.
- **Spotify/ReccoBeats responses:** cache in the DB keyed by track/artist ID so re-syncs and repeat users avoid rate limits and latency.

**SDET specifics (this user cares about evals as a career skill — lean in here):**
- **Unit tests for the profile math (pytest).** These are the highest-value tests because the math is deterministic: given a fixed set of feature vectors, assert the centroid, z-scores, k-means labels (with fixed `random_state`), and cosine similarities equal known values. Test `profile_to_prompt` maps known feature ranges to expected vocabulary ("energy 0.9 → 'energetic'").
- **Integration tests with mocked Spotify/ReccoBeats.** Use **vcrpy** (or the `pytest-recording` plugin) to **record real API responses once** into YAML "cassettes," then **replay** them offline — tests become fast, deterministic, and network-free. Filter the `Authorization` header out of cassettes so tokens aren't committed. The `responses` library is the alternative for hand-crafted mocks (useful for simulating **429/5xx errors** vcrpy can't easily record). Test pagination (0, 50, 51 tracks) and 429 backoff.
- **End-to-end tests.** Drive the full flow against a stubbed generation worker (return a tiny fixed WAV so tests don't wait on a GPU): login → sync → build profile → generate → poll → assert an MP3 URL and valid MP3 header.
- **Generation-quality evals (connect to LLM/generative-model eval concepts).** Generative output has no single "correct" answer, so borrow the modern eval playbook:
  - **Golden datasets:** curate a fixed set of (profile, prompt) → expected-attribute pairs. E.g., "high-energy electronic profile" should yield audio whose **measured** tempo/energy (recomputed with Essentia/librosa) fall in expected ranges — an objective, regression-catching check.
  - **CLAP score:** embed the generated audio and the prompt text with a CLAP (Contrastive Language-Audio Pretraining) model and measure their cosine similarity — a quantitative "does the audio match the words?" metric, analogous to the MusicGen paper's own `CLAP_scr`.
  - **FAD (Fréchet Audio Distance):** distance between feature distributions of generated vs. reference audio — a quality/realism proxy used throughout the literature.
  - **Human/LLM-judge ratings:** a small rubric (relevance, quality) scored by humans or an audio-capable model — the generative-eval equivalent of "LLM-as-judge." Track these over time to catch regressions when you change prompts or model versions.

---

## Recommendations (staged, with decision thresholds)

**Stage 1 — Prove the pipeline (Weeks 1–2).** Ship OAuth+PKCE, Liked-Songs ingestion, and a **metadata-only** taste profile (genres, artists, popularity proxy via track count, release era). Generate with `musicgen-small` **synchronously on a local GPU/Colab** just to see end-to-end audio. *Success threshold:* a real user's library produces a coherent prompt and a playable MP3.

**Stage 2 — Make it robust (Weeks 3–4).** Add the **async job queue** (Celery+Redis), status polling, DB persistence, and the **ReccoBeats enrichment layer** behind a feature flag. Add k-means/GMM clustering + the profile-to-prompt rules. *Threshold to add ReccoBeats permanently:* it reliably returns features for >70% of a typical library; if reliability is poor (users report inconsistency), fall back to **Essentia on 30-second previews** or stay metadata-only.

**Stage 3 — Deploy + evaluate (Weeks 5–6).** Deploy on **Modal** with `musicgen-small`; build the **SDET eval harness** (golden dataset + CLAP score + vcrpy integration tests). *Threshold to upgrade to `musicgen-medium`:* users find small's quality too low **and** your GPU budget tolerates ≥16 GB VRAM and ~2× latency. *Threshold to move off serverless to a dedicated GPU:* sustained utilization >~80% (dedicated becomes cheaper than per-second).

**Stage 4 — Portfolio polish.** Add the PCA/UMAP "taste map" visualization, write up the MusicGen training explanation and the eval methodology in the README — **the evals engineering is your strongest FDE signal**, so make it prominent. Consider LoRA fine-tuning as a clearly-labeled "future work" experiment only.

**Team ownership summary:**
- **UI dev:** OAuth button + redirect handling, library/profile display, prompt input, job-polling spinner, MP3 player, taste-map chart — all coded against the backend's OpenAPI contract.
- **Backend dev:** every endpoint, PKCE/token handling, ingestion+caching, the profile math, the generation worker, storage, model hosting.
- **SDET:** unit tests (profile math), vcrpy integration tests (Spotify/ReccoBeats), e2e tests, and the generation eval harness (golden datasets, CLAP/FAD, LLM-judge rubric).

---

## Packages Summary

| Package | Role | Why chosen |
|---|---|---|
| **spotipy** (spotipy-dev fork, 2.25.1) | Spotify Web API client | Maintained; PKCE via `SpotifyPKCE`; handles pagination, token refresh, caching |
| **httpx** (or `requests`) | HTTP client for ReccoBeats / raw calls | Async-capable (`httpx`), needed where Spotipy doesn't cover (ReccoBeats) |
| **fastapi** | Web framework | Async, typed, auto OpenAPI docs — the contract the UI/SDET build on |
| **uvicorn** | ASGI server | Runs FastAPI in production |
| **pydantic** / **pydantic-settings** | Validation + settings/secrets | Typed request/response models; `.env` secret loading |
| **transformers** | Loads MusicGen | `AutoProcessor` + `MusicgenForConditionalGeneration`; the HF standard |
| **torch** | Deep-learning runtime | Backs transformers; GPU tensor ops |
| **torchaudio** / **audiocraft** | Audio I/O / Meta's MusicGen API | `torchaudio.save`; audiocraft for the native MusicGen interface/melody |
| **numpy** / **scipy** | Numerics + WAV writing | Vector math; `scipy.io.wavfile.write` at 32 kHz |
| **scikit-learn** | Clustering + scaling + PCA | `StandardScaler`, `KMeans`, `GaussianMixture`, `PCA`, silhouette score |
| **umap-learn** | Non-linear 2-D projection | Prettier taste-map viz than PCA |
| **sentence-transformers** | Genre/artist text embeddings | `all-MiniLM-L6-v2`; semantic genre similarity + clustering utilities |
| **pydub** | WAV→MP3 transcode | Simple `AudioSegment.export(format="mp3")` (needs ffmpeg) |
| **ffmpeg** (system) | Audio codec backend | Required by pydub/torchaudio for MP3 |
| **celery** + **redis** (or **arq**) | Async job queue + broker | Decouples long generation from HTTP; retries; independent GPU scaling |
| **SQLAlchemy** + Postgres/SQLite | ORM + persistence | Store profiles, jobs, cached API data |
| **pytest** | Test runner | Foundation for all test tiers |
| **vcrpy** / **pytest-recording** | Record/replay HTTP in tests | Offline, deterministic Spotify/ReccoBeats integration tests |
| **responses** | Hand-crafted HTTP mocks | Simulate 429/5xx errors vcrpy can't easily record |
| **python-dotenv** | Local env loading | Keeps secrets out of code (with pydantic-settings) |

---

## Caveats
- **Spotify audio features are gone for new apps and there is no official replacement** (confirmed via Spotify's own Nov 2024 blog, TechCrunch, and 2026 developer reports). Any plan assuming direct `audio-features` access will fail with 403 — design metadata-first.
- **Third-party feature APIs are approximations.** ReccoBeats/FreqBlog derive values with open tools (Essentia/librosa), so they are "directionally compatible but not byte-identical to Spotify's," and users report ReccoBeats reliability as inconsistent. Re-tune any hard thresholds; treat `speechiness`/`instrumentalness`/`liveness`/`acousticness` as especially rough.
- **The Feb 2026 Dev Mode 5-user cap and Premium-owner requirement** mean this app cannot serve the public without an Extended Quota extension (which requires a large MAU org). It is fine as a personal/portfolio project used by you and a few testers — state this limitation explicitly.
- **MusicGen output is capped at 30 seconds** and licensed **CC-BY-NC** (non-commercial). Generation is partly **single-core-CPU-bound**, so an A100 is often not meaningfully faster than a 3090/4090 for single samples — don't over-provision GPU for a one-at-a-time demo.
- **No official per-size VRAM/latency table exists** for MusicGen; the reliable anchors are Meta's "≥16 GB for medium," the T4 "~35 s per 10 s (small)" datapoint, and Replicate's A100 "~72 s typical." Treat consumer-GPU (3060/4090) times as unbenchmarked estimates.
- **Model/platform churn:** Replicate was acquired by Cloudflare in early 2026; open text-to-music SOTA moves fast (Stable Audio 3, YuE, ACE-Step). Re-verify model availability and pricing at build time.