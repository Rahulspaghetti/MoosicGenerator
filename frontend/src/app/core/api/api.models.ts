/**
 * Typed contract for the FastAPI backend, agreed with Agent B (fastapi-engineer)
 * and confirmed byte-identical by Agent C (qa-overseer) on 2026-07-03.
 *
 * Notes:
 * - `POST /generate` responds `202 Accepted`. Angular's HttpClient treats any
 *   2xx status as success and parses the JSON body normally, so no special
 *   handling is required in ApiService.
 * - `GET /generate/{job_id}` is polled by the studio "running" screen; the
 *   Phase 0 stub deterministically walks pending -> running -> complete.
 */

export interface AuthLoginResponse {
  authorize_url: string;
  state: string;
}

export interface AuthCallbackResponse {
  session_id: string;
  spotify_user_id: string;
  display_name: string;
}

export interface Playlist {
  id: string;
  name: string;
  tracks: number;
  color: string;
}

export interface LibrarySyncResponse {
  liked_count: number;
  playlists: Playlist[];
  genres: string[];
  synced_at: string;
}

export type LibrarySyncJobStatus = 'pending' | 'running' | 'complete' | 'failed';

/** `POST /library/sync` — the enqueued background job handle. */
export interface LibrarySyncJobResponse {
  job_id: string;
  status: LibrarySyncJobStatus | string;
}

/**
 * `POST /library/sync` response: either a fresh stored profile is served
 * (`cached: true`, `profile` set) or a background job is enqueued to poll
 * (`cached: false`, `job_id` set).
 */
export interface LibrarySyncStartResponse {
  cached: boolean;
  status: string;
  job_id: string | null;
  profile: LibrarySyncResponse | null;
}

/** `GET /library/sync/{job_id}` — polled until `complete` or `failed`. */
export interface LibrarySyncStatusResponse {
  job_id: string;
  status: LibrarySyncJobStatus | string;
  processed: number;
  total: number;
  /** Partial fingerprint (populated while running). */
  liked_count: number;
  genres: string[];
  result: LibrarySyncResponse | null;
  error: string | null;
}

export interface ProfileBuildResponse {
  profile_id: string;
  status: string;
}

export interface ProfileSummary {
  top_genres: string[];
  track_count: number;
  eclecticness: number;
}

export interface ProfileCluster {
  label: string;
  size: number;
  descriptor: string;
}

export interface ProfileVizPoint {
  x: number;
  y: number;
  label: string;
}

export interface ProfileResponse {
  summary: ProfileSummary;
  clusters: ProfileCluster[];
  viz: ProfileVizPoint[];
}

export interface GenerateRequest {
  session_id: string;
  prompt: string;
  lyrics?: string;
  enhance_lyrics: boolean;
  reference_sample_ids: string[];
}

export type GenerateJobStatus = 'pending' | 'running' | 'complete' | 'failed';

export interface GenerateResponse {
  job_id: string;
  status: GenerateJobStatus | string;
}

export interface GenerateStatusResponse {
  job_id: string;
  status: GenerateJobStatus | string;
  progress: number;
  step: string | null;
  url: string | null;
  error: string | null;
}
