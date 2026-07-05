import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { Callback } from './callback';
import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import {
  AuthCallbackResponse,
  LibrarySyncResponse,
  LibrarySyncStartResponse,
  LibrarySyncStatusResponse,
} from '../../core/api/api.models';

function activatedRouteStub(queryParams: Record<string, string>) {
  return { snapshot: { queryParamMap: convertToParamMap(queryParams) } };
}

describe('Callback', () => {
  let apiMock: {
    authCallback: ReturnType<typeof vi.fn>;
    librarySync: ReturnType<typeof vi.fn>;
    getLibrarySyncStatus: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    sessionStorage.clear();
    apiMock = { authCallback: vi.fn(), librarySync: vi.fn(), getLibrarySyncStatus: vi.fn() };
  });

  afterEach(() => sessionStorage.clear());

  /** Configures the module and constructs the component *without* running ngOnInit yet. */
  async function setup(
    queryParams: Record<string, string>,
  ): Promise<{ fixture: ComponentFixture<Callback>; authStore: AuthStore }> {
    await TestBed.configureTestingModule({
      imports: [Callback],
      providers: [
        provideRouter([]),
        { provide: Api, useValue: apiMock },
        { provide: ActivatedRoute, useValue: activatedRouteStub(queryParams) },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(Callback);
    const authStore = TestBed.inject(AuthStore);
    return { fixture, authStore };
  }

  it('exchanges the code, starts the background sync, and goes straight to /studio', async () => {
    const session: AuthCallbackResponse = {
      session_id: 'sess_1',
      spotify_user_id: 'spotify_1',
      display_name: 'Ada Lovelace',
    };
    const job: LibrarySyncStartResponse = {
      cached: false,
      status: 'pending',
      job_id: 'lib_1',
      profile: null,
    };
    const library: LibrarySyncResponse = {
      liked_count: 10,
      playlists: [],
      genres: ['synthwave'],
      synced_at: new Date().toISOString(),
    };
    const complete: LibrarySyncStatusResponse = {
      job_id: 'lib_1',
      status: 'complete',
      processed: 3,
      total: 3,
      liked_count: 10,
      genres: ['synthwave'],
      result: library,
      error: null,
    };
    apiMock.authCallback.mockReturnValue(of(session));
    apiMock.librarySync.mockReturnValue(of(job));
    apiMock.getLibrarySyncStatus.mockReturnValue(of(complete));

    const { fixture, authStore } = await setup({ code: 'abc', state: 'xyz' });
    authStore.setPendingOAuthState('xyz');

    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    fixture.detectChanges();
    // Session + navigation happen immediately; the sync polls in the background.
    expect(apiMock.authCallback).toHaveBeenCalledWith('abc', 'xyz');
    expect(apiMock.librarySync).toHaveBeenCalledWith('sess_1');
    expect(authStore.sessionId()).toBe('sess_1');
    expect(navigateSpy).toHaveBeenCalledWith(['/studio']);

    // Let SyncStore's timer(0) fire the first poll → completes → library stored.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(apiMock.getLibrarySyncStatus).toHaveBeenCalledWith('lib_1');
    expect(authStore.spotifyConnected()).toBe(true);
  });

  it('uses the cached profile for a returning user and skips polling', async () => {
    const session: AuthCallbackResponse = {
      session_id: 'sess_1',
      spotify_user_id: 'spotify_1',
      display_name: 'Ada Lovelace',
    };
    const library: LibrarySyncResponse = {
      liked_count: 42,
      playlists: [],
      genres: ['jazz'],
      synced_at: new Date().toISOString(),
    };
    const cached: LibrarySyncStartResponse = {
      cached: true,
      status: 'cached',
      job_id: null,
      profile: library,
    };
    apiMock.authCallback.mockReturnValue(of(session));
    apiMock.librarySync.mockReturnValue(of(cached));

    const { fixture, authStore } = await setup({ code: 'abc', state: 'xyz' });
    authStore.setPendingOAuthState('xyz');

    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    fixture.detectChanges();

    expect(apiMock.getLibrarySyncStatus).not.toHaveBeenCalled();
    expect(authStore.spotifyConnected()).toBe(true);
    expect(navigateSpy).toHaveBeenCalledWith(['/studio']);
  });

  it('shows an error and does not call the API when the state does not match (CSRF check)', async () => {
    const { fixture, authStore } = await setup({ code: 'abc', state: 'tampered-state' });
    authStore.setPendingOAuthState('expected-state');

    fixture.detectChanges();

    expect(apiMock.authCallback).not.toHaveBeenCalled();
    const alert = fixture.nativeElement.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('could not be verified');
  });

  it('shows an error when Spotify denies the authorization', async () => {
    const { fixture } = await setup({ error: 'access_denied' });
    fixture.detectChanges();

    expect(apiMock.authCallback).not.toHaveBeenCalled();
    const alert = fixture.nativeElement.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('cancelled');
  });

  it('shows an error when the backend call fails', async () => {
    apiMock.authCallback.mockReturnValue(throwError(() => new Error('network down')));

    const { fixture, authStore } = await setup({ code: 'abc', state: 'xyz' });
    authStore.setPendingOAuthState('xyz');

    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('could not finish connecting');
  });
});
