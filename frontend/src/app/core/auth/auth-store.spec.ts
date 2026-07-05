import { TestBed } from '@angular/core/testing';

import { AuthStore } from './auth-store';

describe('AuthStore', () => {
  let service: AuthStore;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({});
    service = TestBed.inject(AuthStore);
  });

  afterEach(() => sessionStorage.clear());

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('starts disconnected', () => {
    expect(service.hasSession()).toBe(false);
    expect(service.spotifyConnected()).toBe(false);
  });

  it('becomes spotifyConnected only once the library has synced', () => {
    service.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada' });
    expect(service.spotifyConnected()).toBe(false);

    service.setLibrarySync({ liked_count: 3, playlists: [], genres: [], synced_at: new Date().toISOString() });
    expect(service.spotifyConnected()).toBe(true);
  });

  it('round-trips the pending OAuth state exactly once (consume clears it)', () => {
    service.setPendingOAuthState('csrf-token');
    expect(service.consumePendingOAuthState()).toBe('csrf-token');
    expect(service.consumePendingOAuthState()).toBeNull();
  });

  it('persists state across a fresh AuthStore instance via sessionStorage (survives OAuth redirect reload)', () => {
    service.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada' });
    service.setLibrarySync({ liked_count: 3, playlists: [], genres: [], synced_at: new Date().toISOString() });

    // Flush the persistence effects, then simulate a full page reload: a
    // brand-new injector reads the (now-written) sessionStorage from scratch.
    TestBed.tick();
    const rehydrated = TestBed.runInInjectionContext(() => new AuthStore());

    expect(rehydrated.sessionId()).toBe('s1');
    expect(rehydrated.hasSession()).toBe(true);
    expect(rehydrated.spotifyConnected()).toBe(true);
  });

  it('reset() clears all session state', () => {
    service.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada' });
    service.reset();

    expect(service.sessionId()).toBeNull();
    expect(service.hasSession()).toBe(false);
    expect(service.spotifyConnected()).toBe(false);
  });
});
