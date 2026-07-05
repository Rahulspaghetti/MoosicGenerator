import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

export interface AccentOption {
  readonly value: string;
  readonly label: string;
}

/** The 4 configurable accent options from design/THEME.md. */
export const ACCENT_OPTIONS: readonly AccentOption[] = [
  { value: '#6a8fe0', label: 'Blue' },
  { value: '#34d0c0', label: 'Teal' },
  { value: '#c07cf0', label: 'Purple' },
  { value: '#d8a24a', label: 'Amber' },
] as const;

const DEFAULT_ACCENT = ACCENT_OPTIONS[0].value;

/**
 * Lightens a `#rrggbb` hex color 40% toward white:
 * `c' = c + (255 - c) * 0.4` applied per RGB channel.
 */
export function accentLightOf(hex: string): string {
  const normalized = hex.replace('#', '');
  const r = parseInt(normalized.substring(0, 2), 16);
  const g = parseInt(normalized.substring(2, 4), 16);
  const b = parseInt(normalized.substring(4, 6), 16);

  const lighten = (channel: number): number => Math.round(channel + (255 - channel) * 0.4);
  const toHex = (channel: number): string => lighten(channel).toString(16).padStart(2, '0');

  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Central theme state for the Overtone design system.
 * `accentColor` drives every CTA, focus ring, active toggle, progress bar and
 * waveform in the app; `accentLight` is derived from it via `computed()`.
 * Both are written onto `:root` as CSS custom properties so plain CSS /
 * Tailwind utilities (`bg-accent`, `text-accent`, ...) stay in sync.
 */
@Injectable({
  providedIn: 'root',
})
export class Theme {
  private readonly document = inject(DOCUMENT);

  readonly brandName = signal('SpaghettiTunes');
  readonly accentOptions = ACCENT_OPTIONS;
  readonly accentColor = signal<string>(DEFAULT_ACCENT);
  readonly accentLight = computed(() => accentLightOf(this.accentColor()));

  /** Studio defaults (design/THEME.md "Configurable Props"). */
  readonly defaultLyricsOn = signal(false);
  readonly autoEnhanceDefault = signal(true);

  constructor() {
    effect(() => {
      const root = this.document.documentElement;
      root.style.setProperty('--accent', this.accentColor());
      root.style.setProperty('--accent-light', this.accentLight());
    });
  }

  setAccentColor(value: string): void {
    this.accentColor.set(value);
  }
}
