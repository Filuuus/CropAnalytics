import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';

export type UserRole = 'SADMIN' | 'JEFE' | 'INVESTIGADOR';
export type AuthProvider = 'local' | 'google';

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  provider: AuthProvider;
  avatar?: string | null;
  is_active: boolean;
  date_joined?: string;
  is_initial_jefe?: boolean;
  can_change_role?: boolean;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: AuthUser;
  role: UserRole;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly accessKey = 'ca_access_token';
  private readonly refreshKey = 'ca_refresh_token';
  private readonly userKey = 'ca_user';

  private readonly accessToken = signal<string | null>(localStorage.getItem(this.accessKey));
  private readonly refreshToken = signal<string | null>(localStorage.getItem(this.refreshKey));

  readonly currentUser = signal<AuthUser | null>(this.readUser());
  readonly isAuthenticated = computed(() => !!this.accessToken() && !!this.currentUser());
  readonly role = computed(() => this.currentUser()?.role ?? null);

  register(payload: { name: string; email: string; password: string }): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${environment.apiUrl}/auth/register/`, payload)
      .pipe(tap((response) => this.setSession(response)));
  }

  login(payload: { email: string; password: string }): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${environment.apiUrl}/auth/login/`, payload)
      .pipe(tap((response) => this.setSession(response)));
  }

  googleLogin(credential: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${environment.apiUrl}/auth/google/`, { credential })
      .pipe(tap((response) => this.setSession(response)));
  }

  refreshAccessToken(): Observable<{ access: string; refresh?: string }> {
    return this.http
      .post<{ access: string; refresh?: string }>(`${environment.apiUrl}/auth/token/refresh/`, {
        refresh: this.getRefreshToken(),
      })
      .pipe(
        tap((response) => {
          localStorage.setItem(this.accessKey, response.access);
          this.accessToken.set(response.access);
          if (response.refresh) {
            localStorage.setItem(this.refreshKey, response.refresh);
            this.refreshToken.set(response.refresh);
          }
        }),
      );
  }

  loadCurrentUser(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${environment.apiUrl}/auth/me/`).pipe(
      tap((user) => {
        localStorage.setItem(this.userKey, JSON.stringify(user));
        this.currentUser.set(user);
      }),
    );
  }

  logout(): void {
    const refresh = this.getRefreshToken();
    if (refresh) {
      this.http.post(`${environment.apiUrl}/auth/logout/`, { refresh }).subscribe({ error: () => undefined });
    }
    localStorage.removeItem(this.accessKey);
    localStorage.removeItem(this.refreshKey);
    localStorage.removeItem(this.userKey);
    this.accessToken.set(null);
    this.refreshToken.set(null);
    this.currentUser.set(null);
    this.router.navigate(['/auth/login']);
  }

  getAccessToken(): string | null {
    return this.accessToken();
  }

  getRefreshToken(): string | null {
    return this.refreshToken();
  }

  setSession(response: AuthResponse): void {
    localStorage.setItem(this.accessKey, response.access);
    localStorage.setItem(this.refreshKey, response.refresh);
    localStorage.setItem(this.userKey, JSON.stringify(response.user));
    this.accessToken.set(response.access);
    this.refreshToken.set(response.refresh);
    this.currentUser.set(response.user);
  }

  hasAnyRole(roles: UserRole[]): boolean {
    const role = this.role();
    return !!role && roles.includes(role);
  }

  dashboardFor(role: UserRole | null = this.role()): string {
    if (role === 'INVESTIGADOR') {
      return '/dashboard-investigador';
    }
    return '/dashboard-jefe';
  }

  redirectByRole(): void {
    this.router.navigate([this.dashboardFor()]);
  }

  private readUser(): AuthUser | null {
    const raw = localStorage.getItem(this.userKey);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      localStorage.removeItem(this.userKey);
      return null;
    }
  }
}
