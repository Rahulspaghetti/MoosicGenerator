import { Component, ElementRef, OnInit, afterRenderEffect, inject, signal, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { switchMap } from 'rxjs';

import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { SyncStore } from '../../core/sync/sync-store';

type CallbackStatus = 'exchanging' | 'syncing' | 'error';

/**
 * Landing page for the Spotify OAuth redirect (`redirect_uri` = `/callback`).
 * Reads `code`/`state` from the query string, exchanges them for a session via
 * `GET /auth/callback`, syncs the library via `POST /library/sync`, then hands
 * control back to the Login screen which renders the "connected" state.
 */
@Component({
  selector: 'app-callback',
  imports: [],
  templateUrl: './callback.html',
  styleUrl: './callback.css',
})
export class Callback implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(Api);
  private readonly authStore = inject(AuthStore);
  private readonly syncStore = inject(SyncStore);

  protected readonly status = signal<CallbackStatus>('exchanging');
  protected readonly errorMessage = signal<string | null>(null);

  /** Only present in the DOM once `status()` is `'error'` (see callback.html). */
  private readonly retryButton = viewChild<ElementRef<HTMLButtonElement>>('retryBtn');

  constructor() {
    // Focus management: once the error state renders, move focus to the
    // recovery action so keyboard/screen-reader users land on it immediately
    // instead of having to hunt for it after the aria-live announcement.
    afterRenderEffect(() => {
      if (this.status() === 'error') {
        this.retryButton()?.nativeElement.focus();
      }
    });
  }

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const deniedReason = params.get('error');
    const code = params.get('code');
    const state = params.get('state');

    if (deniedReason) {
      this.fail('Spotify authorization was cancelled. Please try connecting again.');
      return;
    }
    if (!code || !state) {
      this.fail('Missing authorization details in the redirect. Please try connecting again.');
      return;
    }

    const expectedState = this.authStore.consumePendingOAuthState();
    if (!expectedState || expectedState !== state) {
      this.fail('This connection request could not be verified. Please try again.');
      return;
    }

    this.api
      .authCallback(code, state)
      .pipe(
        switchMap((session) => {
          this.authStore.setSession(session);
          this.status.set('syncing');
          return this.api.librarySync(session.session_id);
        }),
      )
      .subscribe({
        // Either a fresh stored profile came back (returning user — no re-sync)
        // or a background job was started. Either way, go straight to the studio;
        // SyncStore polls the job independently when there is one.
        next: (start) => {
          if (start.cached && start.profile) {
            this.authStore.setLibrarySync(start.profile);
          } else if (start.job_id) {
            this.syncStore.start(start.job_id);
          }
          void this.router.navigate(['/studio']);
        },
        error: () => this.fail('We could not finish connecting to Spotify. Please try again.'),
      });
  }

  protected onRetry(): void {
    void this.router.navigate(['/login']);
  }

  private fail(message: string): void {
    this.status.set('error');
    this.errorMessage.set(message);
    this.authStore.setError(message);
  }
}
