import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { NEVER } from 'rxjs';

import { Login } from './login';
import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { LibrarySyncResponse } from '../../core/api/api.models';
import { expectNoA11yViolations } from '../../../testing/a11y';

describe('Login a11y', () => {
  let fixture: ComponentFixture<Login>;
  let authStore: AuthStore;

  beforeEach(async () => {
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), { provide: Api, useValue: { authLogin: vi.fn(() => NEVER) } }],
    }).compileComponents();

    fixture = TestBed.createComponent(Login);
    authStore = TestBed.inject(AuthStore);
    authStore.reset();
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => sessionStorage.clear());

  it('has zero axe violations in the initial (not-connected) state', async () => {
    await expectNoA11yViolations(fixture.nativeElement);
  });

  it('has zero axe violations while the Spotify connection is pending', async () => {
    (fixture.nativeElement.querySelector('.ov-btn-spotify') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement);
  });

  it('has zero axe violations in the connected state (playlist list + Enter the studio)', async () => {
    const library: LibrarySyncResponse = {
      liked_count: 88,
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

    await expectNoA11yViolations(fixture.nativeElement);
  });
});
