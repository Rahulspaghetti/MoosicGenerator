import { Routes } from '@angular/router';

import { requireConnectionGuard } from './core/auth/require-connection-guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  {
    path: 'login',
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
    title: 'Sign in — SpaghettiTunes',
  },
  {
    path: 'callback',
    loadComponent: () => import('./features/callback/callback').then((m) => m.Callback),
    title: 'Connecting Spotify — SpaghettiTunes',
  },
  {
    path: 'studio',
    loadComponent: () => import('./features/studio/studio').then((m) => m.Studio),
    canActivate: [requireConnectionGuard],
    title: 'Studio — SpaghettiTunes',
  },
  { path: '**', redirectTo: 'login' },
];
