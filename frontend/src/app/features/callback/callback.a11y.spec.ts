import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NEVER, throwError } from 'rxjs';

import { Callback } from './callback';
import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { expectNoA11yViolations } from '../../../testing/a11y';

function activatedRouteStub(queryParams: Record<string, string>) {
  return { snapshot: { queryParamMap: convertToParamMap(queryParams) } };
}

describe('Callback a11y', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  async function setup(queryParams: Record<string, string>, apiMock: Partial<Api>) {
    await TestBed.configureTestingModule({
      imports: [Callback],
      providers: [
        provideRouter([]),
        { provide: Api, useValue: apiMock },
        { provide: ActivatedRoute, useValue: activatedRouteStub(queryParams) },
      ],
    }).compileComponents();

    const fixture: ComponentFixture<Callback> = TestBed.createComponent(Callback);
    const authStore = TestBed.inject(AuthStore);
    return { fixture, authStore };
  }

  it('has zero axe violations in the "connecting" (loading/status) state', async () => {
    // NEVER: an Observable that never emits, so the component stays in its
    // initial "exchanging" status — lets us audit the aria-live/status markup.
    const { fixture, authStore } = await setup(
      { code: 'abc', state: 'xyz' },
      { authCallback: vi.fn(() => NEVER) as unknown as Api['authCallback'] },
    );
    authStore.setPendingOAuthState('xyz');
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement);
  });

  it('has zero axe violations in the error state', async () => {
    const { fixture, authStore } = await setup(
      { code: 'abc', state: 'xyz' },
      { authCallback: vi.fn(() => throwError(() => new Error('boom'))) as unknown as Api['authCallback'] },
    );
    authStore.setPendingOAuthState('xyz');
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement);
  });
});
