import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { Login } from './login';
import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { AuthLoginResponse, LibrarySyncResponse } from '../../core/api/api.models';

describe('Login', () => {
  let fixture: ComponentFixture<Login>;
  let authStore: AuthStore;
  let apiMock: { authLogin: ReturnType<typeof vi.fn> };

  function spotifyButton(): HTMLButtonElement | null {
    return fixture.nativeElement.querySelector('.ov-btn-spotify');
  }

  beforeEach(async () => {
    sessionStorage.clear();
    apiMock = { authLogin: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), { provide: Api, useValue: apiMock }],
    }).compileComponents();

    fixture = TestBed.createComponent(Login);
    authStore = TestBed.inject(AuthStore);
    authStore.reset();
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => sessionStorage.clear());

  it('renders the hero heading', () => {
    const heading: HTMLElement = fixture.nativeElement.querySelector('h1');
    expect(heading.textContent).toContain('Music, tuned to');
    expect(heading.textContent).toContain('taste');
  });

  it('shows an enabled "Continue with Spotify" button as the sole login', () => {
    const btn = spotifyButton();
    expect(btn).not.toBeNull();
    expect(btn?.disabled).toBe(false);
    expect(fixture.nativeElement.textContent).not.toContain('Google');
  });

  it('calls /auth/login and stores the CSRF state when "Continue with Spotify" is clicked', () => {
    const response: AuthLoginResponse = {
      authorize_url: 'https://accounts.spotify.com/authorize?x=1',
      state: 'abc123',
    };
    apiMock.authLogin.mockReturnValue(of(response));
    const setPendingSpy = vi.spyOn(authStore, 'setPendingOAuthState');

    spotifyButton()?.click();

    expect(apiMock.authLogin).toHaveBeenCalledTimes(1);
    expect(setPendingSpy).toHaveBeenCalledWith('abc123');
  });

  it('shows the playlist list and "Enter the studio" CTA once the library is synced', async () => {
    const library: LibrarySyncResponse = {
      liked_count: 120,
      playlists: [
        { id: 'p1', name: 'Late Night Drive', tracks: 42, color: '#334' },
        { id: 'p2', name: 'Focus', tracks: 18, color: '#556' },
      ],
      genres: ['synthwave'],
      synced_at: new Date().toISOString(),
    };
    authStore.setLibrarySync(library);
    fixture.detectChanges();
    await fixture.whenStable();

    const items = fixture.nativeElement.querySelectorAll('li');
    expect(items.length).toBe(2);
    expect(fixture.nativeElement.textContent).toContain('2 imported');
    expect(fixture.nativeElement.textContent).toContain('Enter the studio');
  });

  it('navigates to /studio when "Enter the studio" is clicked', () => {
    authStore.setLibrarySync({
      liked_count: 5,
      playlists: [{ id: 'p1', name: 'Chill', tracks: 3, color: '#123' }],
      genres: [],
      synced_at: new Date().toISOString(),
    });
    fixture.detectChanges();

    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    const enterBtn: HTMLButtonElement = fixture.nativeElement.querySelector('.ov-btn-accent');
    enterBtn.click();

    expect(navigateSpy).toHaveBeenCalledWith(['/studio']);
  });
});
