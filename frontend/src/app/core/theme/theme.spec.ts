import { TestBed } from '@angular/core/testing';

import { ACCENT_OPTIONS, Theme, accentLightOf } from './theme';

describe('Theme', () => {
  let service: Theme;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Theme);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('defaults to the blue accent and brand name "SpaghettiTunes"', () => {
    expect(service.accentColor()).toBe('#6a8fe0');
    expect(service.brandName()).toBe('SpaghettiTunes');
  });

  it('exposes exactly the 4 configurable accent options', () => {
    expect(ACCENT_OPTIONS.map((o) => o.value)).toEqual(['#6a8fe0', '#34d0c0', '#c07cf0', '#d8a24a']);
  });

  it('derives accentLight by lightening each RGB channel 40% toward white', () => {
    expect(accentLightOf('#6a8fe0')).toBe('#a6bcec');
    expect(accentLightOf('#000000')).toBe('#666666');
    expect(accentLightOf('#ffffff')).toBe('#ffffff');
  });

  it('updates accentLight reactively when accentColor changes', () => {
    service.setAccentColor('#34d0c0');
    expect(service.accentColor()).toBe('#34d0c0');
    expect(service.accentLight()).toBe(accentLightOf('#34d0c0'));
  });

  it('writes --accent and --accent-light onto the document root', () => {
    service.setAccentColor('#c07cf0');
    TestBed.tick();
    const root = document.documentElement;
    expect(root.style.getPropertyValue('--accent')).toBe('#c07cf0');
    expect(root.style.getPropertyValue('--accent-light')).toBe(accentLightOf('#c07cf0'));
  });
});
