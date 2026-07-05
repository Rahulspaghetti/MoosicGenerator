import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AuthCallbackResponse,
  AuthLoginResponse,
  GenerateRequest,
  GenerateResponse,
  GenerateStatusResponse,
  LibrarySyncResponse,
  LibrarySyncStartResponse,
  LibrarySyncStatusResponse,
  ProfileBuildResponse,
  ProfileResponse,
} from './api.models';

/** Thin, typed wrapper around the SpaghettiTunes FastAPI backend. */
@Injectable({
  providedIn: 'root',
})
export class Api {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  /** Kicks off Spotify OAuth (PKCE): returns the URL to redirect the browser to. */
  authLogin(): Observable<AuthLoginResponse> {
    return this.http.get<AuthLoginResponse>(`${this.base}/auth/login`);
  }

  /** Exchanges the `code`/`state` query params from the OAuth redirect for a session. */
  authCallback(code: string, state: string): Observable<AuthCallbackResponse> {
    const params = new HttpParams().set('code', code).set('state', state);
    return this.http.get<AuthCallbackResponse>(`${this.base}/auth/callback`, { params });
  }

  /**
   * Serves a fresh stored profile if one exists, else enqueues a background
   * sync. Pass `force` to bypass the cache and re-sync.
   */
  librarySync(sessionId: string, force = false): Observable<LibrarySyncStartResponse> {
    return this.http.post<LibrarySyncStartResponse>(`${this.base}/library/sync`, {
      session_id: sessionId,
      force,
    });
  }

  /** Polls a library-sync job's status/progress/result. */
  getLibrarySyncStatus(jobId: string): Observable<LibrarySyncStatusResponse> {
    return this.http.get<LibrarySyncStatusResponse>(`${this.base}/library/sync/${jobId}`);
  }

  /** Returns the durable stored taste fingerprint for the session's user (404 if none). */
  getLibraryProfile(sessionId: string): Observable<LibrarySyncResponse> {
    const params = new HttpParams().set('session_id', sessionId);
    return this.http.get<LibrarySyncResponse>(`${this.base}/library/profile`, { params });
  }

  /** Computes the taste profile from previously-synced library data. */
  profileBuild(sessionId: string): Observable<ProfileBuildResponse> {
    return this.http.post<ProfileBuildResponse>(`${this.base}/profile/build`, {
      session_id: sessionId,
    });
  }

  /** Returns the profile summary + cluster/viz data for the given session. */
  getProfile(sessionId: string): Observable<ProfileResponse> {
    const params = new HttpParams().set('session_id', sessionId);
    return this.http.get<ProfileResponse>(`${this.base}/profile`, { params });
  }

  /** Enqueues a generation job. Backend responds 202; HttpClient treats 2xx as success. */
  generate(request: GenerateRequest): Observable<GenerateResponse> {
    return this.http.post<GenerateResponse>(`${this.base}/generate`, request);
  }

  /** Polls the status of a generation job. */
  getGenerateStatus(jobId: string): Observable<GenerateStatusResponse> {
    return this.http.get<GenerateStatusResponse>(`${this.base}/generate/${jobId}`);
  }
}
