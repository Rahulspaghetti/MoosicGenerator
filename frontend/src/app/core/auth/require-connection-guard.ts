import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthStore } from './auth-store';

/** Guards `/studio`: bounces back to `/login` unless a Spotify session exists.
 * Uses `hasSession` (not `spotifyConnected`) so the studio is reachable while
 * the library is still syncing in the background. */
export const requireConnectionGuard: CanActivateFn = () => {
  const authStore = inject(AuthStore);
  const router = inject(Router);

  if (authStore.hasSession()) {
    return true;
  }

  return router.createUrlTree(['/login']);
};
