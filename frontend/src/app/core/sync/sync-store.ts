import { Injectable, computed, inject, signal } from '@angular/core';
import { Subscription, switchMap, takeWhile, timer } from 'rxjs';

import { Api } from '../api/api';
import { LibrarySyncJobStatus } from '../api/api.models';
import { AuthStore } from '../auth/auth-store';

/** How often to poll the background library-sync job. */
const POLL_INTERVAL_MS = 1500;

/**
 * Owns the background library-sync job: polls it independently of any route so
 * the user can leave `/callback`, land on the studio, and compose a prompt
 * while the sync finishes. Exposes the partial taste fingerprint (liked count +
 * genres) as it accumulates, and pushes the full library into {@link AuthStore}
 * on completion. A single instance (root-provided) backs the sync dialog too.
 */
@Injectable({ providedIn: 'root' })
export class SyncStore {
  private readonly api = inject(Api);
  private readonly authStore = inject(AuthStore);

  readonly jobId = signal<string | null>(null);
  readonly status = signal<LibrarySyncJobStatus | string | null>(null);
  readonly processed = signal(0);
  readonly total = signal(0);
  readonly likedCount = signal(0);
  readonly genres = signal<string[]>([]);
  readonly error = signal<string | null>(null);
  readonly dismissed = signal(false);

  private sub?: Subscription;

  /** True while the job is still pending/running. */
  readonly active = computed(() => this.status() === 'pending' || this.status() === 'running');

  /** 0–100 once `total` is known. */
  readonly progress = computed(() => {
    const total = this.total();
    return total > 0 ? Math.min(100, Math.round((this.processed() / total) * 100)) : 0;
  });

  /** Whether the background-sync dialog should be shown. */
  readonly showDialog = computed(() => this.status() !== null && !this.dismissed());

  /** Begin polling a job; replaces any in-flight poll. */
  start(jobId: string): void {
    this.sub?.unsubscribe();
    this.jobId.set(jobId);
    this.status.set('pending');
    this.processed.set(0);
    this.total.set(0);
    this.likedCount.set(0);
    this.genres.set([]);
    this.error.set(null);
    this.dismissed.set(false);

    this.sub = timer(0, POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.api.getLibrarySyncStatus(jobId)),
        takeWhile((s) => s.status !== 'complete' && s.status !== 'failed', true),
      )
      .subscribe({
        next: (s) => {
          this.status.set(s.status);
          this.processed.set(s.processed);
          this.total.set(s.total);
          this.likedCount.set(s.liked_count);
          this.genres.set(s.genres);
          if (s.status === 'complete' && s.result) {
            this.authStore.setLibrarySync(s.result);
          } else if (s.status === 'failed') {
            this.error.set(s.error ?? 'Some of your taste data could not be loaded.');
          }
        },
        error: () => {
          this.status.set('failed');
          this.error.set('Lost connection while loading your taste — some data may be missing.');
        },
      });
  }

  /** Hide the dialog (does not stop the underlying sync). */
  dismiss(): void {
    this.dismissed.set(true);
  }
}
