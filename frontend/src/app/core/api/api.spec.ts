import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { Api } from './api';
import { environment } from '../../../environments/environment';
import {
  AuthCallbackResponse,
  AuthLoginResponse,
  GenerateResponse,
  GenerateStatusResponse,
  LibrarySyncResponse,
  LibrarySyncStartResponse,
  LibrarySyncStatusResponse,
  ProfileBuildResponse,
  ProfileResponse,
} from './api.models';

describe('Api', () => {
  let service: Api;
  let httpMock: HttpTestingController;
  const base = environment.apiBaseUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(Api);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('GET /auth/login returns the authorize URL + state', () => {
    const expected: AuthLoginResponse = { authorize_url: 'https://accounts.spotify.com/authorize', state: 's1' };
    let actual: AuthLoginResponse | undefined;

    service.authLogin().subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/auth/login`);
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('GET /auth/callback sends code+state as query params', () => {
    const expected: AuthCallbackResponse = {
      session_id: 'sess_1',
      spotify_user_id: 'user_1',
      display_name: 'Ada Lovelace',
    };
    let actual: AuthCallbackResponse | undefined;

    service.authCallback('code_1', 'state_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(
      (r) => r.url === `${base}/auth/callback` && r.params.get('code') === 'code_1' && r.params.get('state') === 'state_1',
    );
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('POST /library/sync sends { session_id, force } and returns a start response', () => {
    const expected: LibrarySyncStartResponse = {
      cached: false,
      status: 'pending',
      job_id: 'lib_1',
      profile: null,
    };
    let actual: LibrarySyncStartResponse | undefined;

    service.librarySync('sess_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/library/sync`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ session_id: 'sess_1', force: false });
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('GET /library/profile returns the stored fingerprint', () => {
    const expected: LibrarySyncResponse = {
      liked_count: 42,
      playlists: [],
      genres: ['lofi'],
      synced_at: '2026-07-05T00:00:00Z',
    };
    let actual: LibrarySyncResponse | undefined;

    service.getLibraryProfile('sess_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(
      (r) => r.url === `${base}/library/profile` && r.params.get('session_id') === 'sess_1',
    );
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('GET /library/sync/{job_id} returns status/progress/result', () => {
    const expected: LibrarySyncStatusResponse = {
      job_id: 'lib_1',
      status: 'complete',
      processed: 3,
      total: 3,
      liked_count: 42,
      genres: ['lofi'],
      result: {
        liked_count: 42,
        playlists: [{ id: 'p1', name: 'Chill', tracks: 10, color: '#334' }],
        genres: ['lofi'],
        synced_at: '2026-07-05T00:00:00Z',
      },
      error: null,
    };
    let actual: LibrarySyncStatusResponse | undefined;

    service.getLibrarySyncStatus('lib_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/library/sync/lib_1`);
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('POST /profile/build sends { session_id }', () => {
    const expected: ProfileBuildResponse = { profile_id: 'prof_1', status: 'complete' };
    let actual: ProfileBuildResponse | undefined;

    service.profileBuild('sess_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/profile/build`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ session_id: 'sess_1' });
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('GET /profile sends session_id as a query param', () => {
    const expected: ProfileResponse = {
      summary: { top_genres: ['lofi'], track_count: 100, eclecticness: 0.4 },
      clusters: [{ label: 'A', size: 10, descriptor: 'mellow' }],
      viz: [{ x: 0.1, y: 0.2, label: 'A' }],
    };
    let actual: ProfileResponse | undefined;

    service.getProfile('sess_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne((r) => r.url === `${base}/profile` && r.params.get('session_id') === 'sess_1');
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });

  it('POST /generate accepts a 202 response as success', () => {
    const expected: GenerateResponse = { job_id: 'job_1', status: 'pending' };
    let actual: GenerateResponse | undefined;

    service
      .generate({
        session_id: 'sess_1',
        prompt: 'warm synthwave',
        enhance_lyrics: false,
        reference_sample_ids: [],
      })
      .subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/generate`);
    expect(req.request.method).toBe('POST');
    req.flush(expected, { status: 202, statusText: 'Accepted' });

    expect(actual).toEqual(expected);
  });

  it('GET /generate/{job_id} returns job status/progress', () => {
    const expected: GenerateStatusResponse = {
      job_id: 'job_1',
      status: 'running',
      progress: 35,
      step: 'Sketching melody',
      url: null,
      error: null,
    };
    let actual: GenerateStatusResponse | undefined;

    service.getGenerateStatus('job_1').subscribe((res) => (actual = res));

    const req = httpMock.expectOne(`${base}/generate/job_1`);
    expect(req.request.method).toBe('GET');
    req.flush(expected);

    expect(actual).toEqual(expected);
  });
});
