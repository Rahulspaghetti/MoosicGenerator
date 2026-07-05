import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { Theme } from '../../core/theme/theme';

@Component({
  selector: 'app-login',
  imports: [],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected readonly theme = inject(Theme);
  protected readonly authStore = inject(AuthStore);

  protected readonly connectingSpotify = signal(false);
  protected readonly navigatingToStudio = signal(false);

  protected readonly spotifyConnected = this.authStore.spotifyConnected;

  protected readonly spotifyLabel = computed(() =>
    this.connectingSpotify() ? 'Connecting…' : 'Continue with Spotify',
  );

  protected readonly playlistCount = computed(() => this.authStore.librarySync()?.playlists.length ?? 0);
  protected readonly playlists = computed(() => this.authStore.librarySync()?.playlists ?? []);

  protected onSpotify(): void {
    if (this.connectingSpotify() || this.authStore.spotifyConnected()) {
      return;
    }
    this.connectingSpotify.set(true);
    this.authStore.setError(null);

    this.api.authLogin().subscribe({
      next: (res) => {
        this.authStore.setPendingOAuthState(res.state);
        // Full browser redirect — the app reloads fresh at /callback.
        window.location.href = res.authorize_url;
      },
      error: () => {
        this.connectingSpotify.set(false);
        this.authStore.setError('Could not start the Spotify connection. Please try again.');
      },
    });
  }

  protected onEnterStudio(): void {
    this.navigatingToStudio.set(true);
    void this.router.navigate(['/studio']);
  }
}
