import { Injectable, computed, effect, signal } from '@angular/core';

import { AuthCallbackResponse, LibrarySyncResponse } from '../api/api.models';

const STORAGE_KEYS = {
  sessionId: 'ov_session_id',
  spotifyUserId: 'ov_spotify_user_id',
  displayName: 'ov_display_name',
  library: 'ov_library_sync',
  oauthState: 'ov_oauth_state',
} as const;

function readSessionStorage(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSessionStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      sessionStorage.removeItem(key);
    } else {
      sessionStorage.setItem(key, value);
    }
  } catch {
    // sessionStorage unavailable (e.g. private mode) — state simply won't survive a reload.
  }
}

/**
 * Holds the login/session state machine (`googleDone`, `spotifyConnected`,
 * synced library, ...) for the app.
 *
 * A real Spotify OAuth round trip is a *full page navigation* away and back
 * (browser -> accounts.spotify.com -> /callback), so every signal here is
 * seeded from `sessionStorage` on construction and persisted on every change,
 * making the login flow survive the reload that happens at `/callback`.
 */
@Injectable({
  providedIn: 'root',
})
export class AuthStore {
  readonly sessionId = signal(readSessionStorage(STORAGE_KEYS.sessionId));
  readonly spotifyUserId = signal(readSessionStorage(STORAGE_KEYS.spotifyUserId));
  readonly displayName = signal(readSessionStorage(STORAGE_KEYS.displayName));
  readonly librarySync = signal<LibrarySyncResponse | null>(readLibraryFromStorage());
  readonly error = signal<string | null>(null);

  /** True once the library has fully synced (drives the login "connected" view). */
  readonly spotifyConnected = computed(() => this.librarySync() !== null);

  /** True as soon as an authenticated session exists — enough to enter the studio
   * and compose while the library syncs in the background. */
  readonly hasSession = computed(() => this.sessionId() !== null);

  constructor() {
    effect(() => writeSessionStorage(STORAGE_KEYS.sessionId, this.sessionId()));
    effect(() => writeSessionStorage(STORAGE_KEYS.spotifyUserId, this.spotifyUserId()));
    effect(() => writeSessionStorage(STORAGE_KEYS.displayName, this.displayName()));
    effect(() => {
      const library = this.librarySync();
      writeSessionStorage(STORAGE_KEYS.library, library ? JSON.stringify(library) : null);
    });
  }

  setSession(session: AuthCallbackResponse): void {
    this.sessionId.set(session.session_id);
    this.spotifyUserId.set(session.spotify_user_id);
    this.displayName.set(session.display_name);
  }

  setLibrarySync(library: LibrarySyncResponse): void {
    this.librarySync.set(library);
    this.error.set(null);
  }

  setError(message: string | null): void {
    this.error.set(message);
  }

  /** Stores the CSRF `state` returned by `/auth/login` just before redirecting to Spotify. */
  setPendingOAuthState(state: string): void {
    writeSessionStorage(STORAGE_KEYS.oauthState, state);
  }

  /** Reads and clears the pending OAuth `state`, for one-time verification in `/callback`. */
  consumePendingOAuthState(): string | null {
    const value = readSessionStorage(STORAGE_KEYS.oauthState);
    writeSessionStorage(STORAGE_KEYS.oauthState, null);
    return value;
  }

  /** Clears all session/login state (e.g. on a failed callback, or explicit sign-out). */
  reset(): void {
    this.sessionId.set(null);
    this.spotifyUserId.set(null);
    this.displayName.set(null);
    this.librarySync.set(null);
    this.error.set(null);
    writeSessionStorage(STORAGE_KEYS.oauthState, null);
  }
}

function readLibraryFromStorage(): LibrarySyncResponse | null {
  const raw = readSessionStorage(STORAGE_KEYS.library);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as LibrarySyncResponse;
  } catch {
    return null;
  }
}
