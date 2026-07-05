import { Component, inject } from '@angular/core';

import { SyncStore } from '../../core/sync/sync-store';

/**
 * Small, non-blocking floating card that reports background library-sync
 * progress. Bound to the root {@link SyncStore}, so it reflects the same job
 * the studio's fingerprint reads. The user can keep composing while it runs,
 * and dismiss it at any time.
 */
@Component({
  selector: 'app-sync-dialog',
  imports: [],
  templateUrl: './sync-dialog.html',
  styleUrl: './sync-dialog.css',
})
export class SyncDialog {
  protected readonly sync = inject(SyncStore);
}
