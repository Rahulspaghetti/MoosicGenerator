import { Component, computed, inject, signal } from '@angular/core';

import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { SyncStore } from '../../core/sync/sync-store';
import { Theme } from '../../core/theme/theme';
import { SyncDialog } from '../sync-dialog/sync-dialog';

/**
 * Studio prompt screen. Reachable as soon as a Spotify session exists — the
 * library keeps syncing in the background (see {@link SyncStore} + the sync
 * dialog), and the taste fingerprint shown here fills in live. The user can
 * compose a prompt immediately with whatever fingerprint has arrived.
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

  protected readonly prompt = signal('');
  protected readonly generating = signal(false);
  protected readonly queuedJobId = signal<string | null>(null);
  protected readonly genError = signal<string | null>(null);

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

  protected setPrompt(event: Event): void {
    this.prompt.set((event.target as HTMLTextAreaElement).value);
  }

  protected onGenerate(): void {
    const sessionId = this.authStore.sessionId();
    if (!this.canGenerate() || !sessionId) {
      return;
    }
    this.generating.set(true);
    this.genError.set(null);
    this.queuedJobId.set(null);

    this.api
      .generate({
        session_id: sessionId,
        prompt: this.prompt().trim(),
        enhance_lyrics: false,
        reference_sample_ids: [],
      })
      .subscribe({
        next: (res) => {
          this.generating.set(false);
          this.queuedJobId.set(res.job_id);
        },
        error: () => {
          this.generating.set(false);
          this.genError.set('Could not queue your track. Please try again.');
        },
      });
  }
}
