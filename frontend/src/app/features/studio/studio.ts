import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, timer } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

import { environment } from '../../../environments/environment';
import { Api } from '../../core/api/api';
import { GenerateStatusResponse } from '../../core/api/api.models';
import { AuthStore } from '../../core/auth/auth-store';
import { SyncStore } from '../../core/sync/sync-store';
import { Theme } from '../../core/theme/theme';
import { SyncDialog } from '../sync-dialog/sync-dialog';

/** Poll interval (ms) for a running generation job. */
const POLL_INTERVAL_MS = 2000;

function isTerminal(status: string): boolean {
  return status === 'complete' || status === 'failed';
}

/**
 * Studio prompt screen. Reachable as soon as a Spotify session exists — the
 * library keeps syncing in the background (see {@link SyncStore} + the sync
 * dialog), and the taste fingerprint shown here fills in live. The user can
 * compose a prompt immediately with whatever fingerprint has arrived, then
 * generate a track: the component queues the job, polls its status, and renders
 * an audio player once the MP3 is ready.
 */
@Component({
  selector: 'app-studio',
  imports: [SyncDialog],
  templateUrl: './studio.html',
  styleUrl: './studio.css',
})
export class Studio {
  protected readonly authStore = inject(AuthStore);
  protected readonly theme = inject(Theme);
  protected readonly sync = inject(SyncStore);
  private readonly api = inject(Api);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly prompt = signal('');
  protected readonly generating = signal(false);
  protected readonly genStatus = signal<GenerateStatusResponse | null>(null);
  private readonly queueError = signal<string | null>(null);
  private pollSub: Subscription | null = null;

  /** Genres: live partial from the running sync, else the persisted full library. */
  protected readonly genres = computed(() => {
    const live = this.sync.genres();
    return live.length ? live : (this.authStore.librarySync()?.genres ?? []);
  });
  protected readonly likedCount = computed(
    () => this.sync.likedCount() || (this.authStore.librarySync()?.liked_count ?? 0),
  );
  protected readonly stillSyncing = this.sync.active;

  protected readonly canGenerate = computed(
    () => this.prompt().trim().length > 0 && !this.generating(),
  );

  /** Current step/progress text while a job runs. */
  protected readonly genStep = computed(() => this.genStatus()?.step ?? null);
  protected readonly genProgress = computed(() =>
    Math.round((this.genStatus()?.progress ?? 0) * 100),
  );

  /** Absolute URL of the finished MP3, or null until the job completes. */
  protected readonly audioUrl = computed(() => {
    const status = this.genStatus();
    return status?.status === 'complete' && status.url
      ? `${environment.apiBaseUrl}${status.url}`
      : null;
  });

  /** Queue failure, or a failed job's error message. */
  protected readonly errorMessage = computed(() => {
    const queue = this.queueError();
    if (queue) {
      return queue;
    }
    const status = this.genStatus();
    return status?.status === 'failed' ? (status.error ?? 'Generation failed.') : null;
  });

  protected setPrompt(event: Event): void {
    this.prompt.set((event.target as HTMLTextAreaElement).value);
  }

  protected onGenerate(): void {
    const sessionId = this.authStore.sessionId();
    if (!this.canGenerate() || !sessionId) {
      return;
    }
    this.generating.set(true);
    this.queueError.set(null);
    this.genStatus.set(null);
    this.pollSub?.unsubscribe();

    this.api
      .generate({
        session_id: sessionId,
        prompt: this.prompt().trim(),
        enhance_lyrics: false,
        reference_sample_ids: [],
      })
      .subscribe({
        next: (res) => this.startPolling(res.job_id),
        error: () => {
          this.generating.set(false);
          this.queueError.set('Could not queue your track. Please try again.');
        },
      });
  }

  private startPolling(jobId: string): void {
    this.pollSub = timer(0, POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.api.getGenerateStatus(jobId)),
        takeWhile((status) => !isTerminal(status.status), true),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (status) => {
          this.genStatus.set(status);
          if (isTerminal(status.status)) {
            this.generating.set(false);
          }
        },
        error: () => {
          this.generating.set(false);
          this.queueError.set('Lost contact while generating. Please try again.');
        },
      });
  }
}
