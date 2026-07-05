# Overtone — Design Theme (source of truth for Agent A)

Distilled from `design/Overtone.dc.html` (the Claude Design "Overtone" component for the
taste-conditioned music-gen app in `artifact.md`). Agent A reimplements this as production
**Angular** (standalone, Signals, Tailwind) — pixel-faithful, WCAG AA, AXE-clean.

`Overtone.dc.html` is a React preview format (`<x-dc>`, `{{ }}`, `sc-if`, `sc-for`). Do NOT ship
it. Read it as the visual reference; build real Angular components.

## Design Tokens

### Typography
- **Display / headings:** `'Playfair Display', serif` — weights 500–800, italic used for accents ("your", status text). h1 44px (login) / 40px (studio) / 36px (done); h2 27px italic.
- **UI / body:** `'Manrope', system-ui, sans-serif` — weights 400–800. Base 18px. Labels 15px/700. Meta 13.5–14.5px.
- Load via Google Fonts (already in the `<helmet>`). `font-variant-numeric: tabular-nums` on timers/counts.

### Color
| Token | Value |
|-------|-------|
| `--bg` | `#05070d` |
| page gradient | `radial-gradient(1300px 820px at 50% -14%, #1b2a4c, #0d1528 40%, #080d18 76%, #05070d)` |
| `--text` | `#eaf0fb` (also `#f2f6fd`, `#eef2fa`) |
| `--text-muted` | `#8d9bb8` |
| `--text-dim` | `#7d8aa6`, `#6b7893`, `#5c6a86`, `#4e5b76` (descending) |
| `--label` | `#aebbd6` |
| **`--accent`** (configurable) | default `#6a8fe0` · options `#34d0c0` teal, `#c07cf0` purple, `#d8a24a` amber |
| `--accent-light` | accent mixed 40% toward white (compute; see helper) |
| `--success` (Spotify) | `#34e08a` → `#16b866`; badge text `#6ee7a8` |
| `--danger` | `#e8896f` (lyrics-required hint) |
| on-accent text | `#0b1220` / `#06251a` |

### Surfaces
- **Card:** `linear-gradient(158deg, rgba(31,43,71,0.92), rgba(14,20,36,0.94))`, border `1px solid rgba(150,170,210,0.16)`, shadow `inset 0 1px 0 rgba(255,255,255,0.06), 0 24px 60px rgba(0,0,0,0.5)`.
- **Inset field:** bg `rgba(10,15,28,0.75)`, border `rgba(150,170,210,0.18)`, `inset 0 1px 3px rgba(0,0,0,0.35)`.
- **Subtle row/panel:** `rgba(18,26,46,0.6)` / `rgba(20,28,48,0.5)`; borders `rgba(150,170,210,0.10–0.28)`.

### Radii / Spacing
- Buttons & inputs `12–14px`; cards `18–22px`; pills/toggles `999px`; icon tiles `9–15px`.
- Containers: topbar `max-w 1180`, login `460`, studio `700`. Topbar pad `22px 40px`.

### Elevation (buttons)
- Neutral: `inset 0 1px 0 rgba(255,255,255,0.12), 0 6px 16px rgba(0,0,0,0.35)`.
- Accent CTA: `linear-gradient(180deg, var(--accent-light), var(--accent))` + `inset 0 1px 0 rgba(255,255,255,0.5), 0 8–10px 22–26px rgba(0,0,0,0.35)`.
- Hover `filter: brightness(1.05–1.08)`; active `transform: scale(0.985–0.99)`.

### Motion
Standard easing `cubic-bezier(0.32,0.72,0,1)`. Keyframes (prefix `ov-`): `fade-up` (.5–.6s entrance), `spin`/`spin-rev` (24s orbit), `disc` (3.4s), `ripple` (2.6s), `eq` (equalizer), `glow` (2.4s), `float`. **Respect `prefers-reduced-motion`** — gate the looping animations (A11y requirement, not in the mock).

### accent-light helper (port to TS)
Lighten each RGB channel 40% toward 255: `c + (255-c)*0.4`. Provide a `computed()` signal deriving `--accent-light` from the selected `--accent`.

## Configurable Props (expose as inputs / theme config)
- `brandName` — default **"SpaghettiTunes"** (mock brand; wordmark uses Playfair gradient text).
- `accentColor` — one of the 4 above; drives every CTA, focus ring, active toggle, progress, waveform.
- `defaultLyricsOn` (bool), `autoEnhanceDefault` (bool) — studio defaults.

## Screens / Components to build
1. **Shell** — page gradient bg, two decorative radial glows + faint diagonal line texture (`pointer-events:none`), topbar (logo tile + gradient wordmark, "Spotify connected" pill in studio).
2. **Login** (`phase=login`): hero (`Music, tuned to *your* taste`), auth card → Google button (pending/done states), "then" divider, Spotify connect button (disabled/50% until Google done) → on connect, playlist list + "Enter the studio". Legal footnote.
3. **Studio / idle** (`gen=idle`): prompt textarea (required), reference-sample dashed dropzone + removable chips (≤5, audio/*), "Add lyrics" toggle → lyrics textarea (required when on; danger hint if empty) + "AI enhance" sub-toggle, "Generate track" CTA (disabled until valid).
4. **Studio / running** (`gen=running`): orbit ring of 6 icon tiles + center spinning vinyl + glow + ripples, 9-bar equalizer, Playfair-italic status text cycling steps, progress bar. Steps: Reading taste profile → Sketching melody → Arranging instruments → Layering harmonies → (Writing vocal line, if lyrics) → Mixing and mastering.
5. **Studio / done** (`gen=done`): "Track ready" badge, player card (play/pause, title `Untitled No. 1`, meta, 0:24, ~48–56-bar waveform), "Compose another" + "Download".

State machine: `phase: login|studio`, `gen: idle|running|done`. Validation: prompt non-empty; lyrics non-empty when lyrics toggle on.

## Wiring to backend (Agent B contract, from artifact.md)
UI states map to endpoints — confirm exact shapes with Agent B before coding:
- Google/Spotify buttons → `/auth/login` + `/auth/callback` (PKCE).
- Playlist list → `/library/sync` result.
- "Generate track" → `POST /generate` → `{job_id}`; running screen polls `GET /generate/{job_id}`; done screen plays the returned MP3 URL.
