import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { App } from './app';
import { routes } from './app.routes';
import { expectNoA11yViolations } from '../testing/a11y';

/**
 * Full-page audit: Shell (header/main landmarks, skip link, topbar) with the
 * Login screen activated through the real router — the truest representation
 * of what a user (and a screen reader) actually loads at `/login`.
 */
describe('App a11y (Shell + Login, full page)', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => sessionStorage.clear());

  it('has zero axe violations at /login', async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes)],
    }).compileComponents();

    const fixture = TestBed.createComponent(App);
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement, 'page');
  });
});
