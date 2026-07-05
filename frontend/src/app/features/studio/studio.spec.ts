import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Studio } from './studio';
import { AuthStore } from '../../core/auth/auth-store';

describe('Studio', () => {
  let component: Studio;
  let fixture: ComponentFixture<Studio>;

  beforeEach(async () => {
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Studio],
      providers: [provideHttpClient()],
    }).compileComponents();

    fixture = TestBed.createComponent(Studio);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  afterEach(() => sessionStorage.clear());

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('greets the connected user by display name', () => {
    const authStore = TestBed.inject(AuthStore);
    authStore.setSession({ session_id: 's1', spotify_user_id: 'u1', display_name: 'Ada' });
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Welcome, Ada');
  });
});
