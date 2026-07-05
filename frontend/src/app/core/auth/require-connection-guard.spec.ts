import { TestBed } from '@angular/core/testing';
import { UrlTree, provideRouter } from '@angular/router';

import { requireConnectionGuard } from './require-connection-guard';
import { AuthStore } from './auth-store';

describe('requireConnectionGuard', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  afterEach(() => sessionStorage.clear());

  it('blocks /studio and redirects to /login when Spotify is not connected', () => {
    const result = TestBed.runInInjectionContext(() =>
      requireConnectionGuard({} as never, {} as never),
    ) as UrlTree;

    expect(result instanceof UrlTree).toBe(true);
    expect(result.toString()).toBe('/login');
  });

  it('allows /studio as soon as a session exists (before the library finishes syncing)', () => {
    const authStore = TestBed.inject(AuthStore);
    authStore.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada' });

    const result = TestBed.runInInjectionContext(() =>
      requireConnectionGuard({} as never, {} as never),
    );

    expect(result).toBe(true);
  });
});
