import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { Studio } from './studio';
import { AuthStore } from '../../core/auth/auth-store';
import { expectNoA11yViolations } from '../../../testing/a11y';

describe('Studio a11y', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('has zero axe violations (placeholder, no display name yet)', async () => {
    await TestBed.configureTestingModule({
      imports: [Studio],
      providers: [provideHttpClient()],
    }).compileComponents();
    const fixture = TestBed.createComponent(Studio);
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement);
  });

  it('has zero axe violations once connected (greets by display name)', async () => {
    await TestBed.configureTestingModule({
      imports: [Studio],
      providers: [provideHttpClient()],
    }).compileComponents();
    const fixture = TestBed.createComponent(Studio);
    const authStore = TestBed.inject(AuthStore);
    authStore.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada Lovelace' });
    authStore.setLibrarySync({ liked_count: 12, playlists: [], genres: [], synced_at: new Date().toISOString() });
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement);
  });
});
