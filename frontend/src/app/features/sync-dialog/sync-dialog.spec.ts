import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SyncDialog } from './sync-dialog';

describe('SyncDialog', () => {
  let fixture: ComponentFixture<SyncDialog>;

  beforeEach(async () => {
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [SyncDialog],
      providers: [provideHttpClient()],
    }).compileComponents();
    fixture = TestBed.createComponent(SyncDialog);
    fixture.detectChanges();
  });

  afterEach(() => sessionStorage.clear());

  it('creates', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('renders nothing until a sync job is active', () => {
    expect((fixture.nativeElement as HTMLElement).querySelector('.ov-sync-dialog')).toBeNull();
  });
});
