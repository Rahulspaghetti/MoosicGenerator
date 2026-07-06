import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { vi } from 'vitest';

import { Studio } from './studio';
import { Api } from '../../core/api/api';
import { AuthStore } from '../../core/auth/auth-store';
import { GenerateStatusResponse } from '../../core/api/api.models';

function status(partial: Partial<GenerateStatusResponse>): GenerateStatusResponse {
  return {
    job_id: 'job_x',
    status: 'running',
    progress: 0,
    step: null,
    url: null,
    error: null,
    ...partial,
  };
}

describe('Studio', () => {
  let component: Studio;
  let fixture: ComponentFixture<Studio>;

  async function setup(apiOverrides: Record<string, unknown> = {}): Promise<void> {
    const api = {
      generate: () => of({ job_id: 'job_x', status: 'pending' }),
      getGenerateStatus: () =>
        of(status({ status: 'complete', progress: 1, url: '/generate/job_x/audio' })),
      ...apiOverrides,
    };
    await TestBed.configureTestingModule({
      imports: [Studio],
      providers: [provideHttpClient(), { provide: Api, useValue: api }],
    }).compileComponents();

    fixture = TestBed.createComponent(Studio);
    component = fixture.componentInstance;
    TestBed.inject(AuthStore).setSession({
      session_id: 's1',
      spotify_user_id: 'u1',
      display_name: 'Ada',
    });
    fixture.detectChanges();
  }

  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    vi.useRealTimers();
    sessionStorage.clear();
  });

  it('should create', async () => {
    await setup();
    expect(component).toBeTruthy();
  });

  it('greets the connected user by display name', async () => {
    await setup();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Welcome, Ada');
  });

  it('polls generation and renders an audio player on complete', async () => {
    let calls = 0;
    await setup({
      getGenerateStatus: () => {
        calls += 1;
        return of(
          calls < 2
            ? status({ status: 'running', progress: 0.4, step: 'Composing' })
            : status({ status: 'complete', progress: 1, url: '/generate/job_x/audio' }),
        );
      },
    });

    vi.useFakeTimers();
    (component as unknown as { prompt: { set(v: string): void } }).prompt.set('warm synthwave');
    (component as unknown as { onGenerate(): void }).onGenerate();

    await vi.advanceTimersByTimeAsync(0); // first poll -> running
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Composing');

    await vi.advanceTimersByTimeAsync(2000); // second poll -> complete
    fixture.detectChanges();

    const audio = (fixture.nativeElement as HTMLElement).querySelector('audio');
    expect(audio).toBeTruthy();
    expect(audio!.getAttribute('src')).toContain('/generate/job_x/audio');
  });

  it('shows an error when generation fails', async () => {
    await setup({
      getGenerateStatus: () => of(status({ status: 'failed', error: 'CUDA GPU required' })),
    });

    vi.useFakeTimers();
    (component as unknown as { prompt: { set(v: string): void } }).prompt.set('warm synthwave');
    (component as unknown as { onGenerate(): void }).onGenerate();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();

    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('CUDA GPU required');
  });
});
