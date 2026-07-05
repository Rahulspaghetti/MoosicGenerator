import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Shell } from './shell';
import { expectNoA11yViolations } from '../../testing/a11y';

describe('Shell a11y', () => {
  it('has zero axe violations with no route active', async () => {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [provideRouter([])],
    }).compileComponents();

    const fixture = TestBed.createComponent(Shell);
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement, 'page');
  });

  it('has zero axe violations with the "Spotify connected" pill shown (studio route)', async () => {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [provideRouter([{ path: 'studio', children: [] }])],
    }).compileComponents();

    const fixture = TestBed.createComponent(Shell);
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/studio');
    fixture.detectChanges();
    await fixture.whenStable();

    await expectNoA11yViolations(fixture.nativeElement, 'page');
  });
});
