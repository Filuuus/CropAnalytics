import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthUser, UserRole } from '../../auth/services/auth.service';

export interface UserFilters {
  search?: string;
  role?: UserRole | '';
  is_active?: string;
}

@Injectable({ providedIn: 'root' })
export class AdminUsersService {
  private readonly http = inject(HttpClient);

  list(filters: UserFilters): Observable<AuthUser[]> {
    let params = new HttpParams();
    if (filters.search) {
      params = params.set('search', filters.search);
    }
    if (filters.role) {
      params = params.set('role', filters.role);
    }
    if (filters.is_active) {
      params = params.set('is_active', filters.is_active);
    }
    return this.http.get<AuthUser[]>(`${environment.apiUrl}/users/`, { params });
  }

  setRole(id: number, role: Exclude<UserRole, 'SADMIN'>): Observable<AuthUser> {
    return this.http.patch<AuthUser>(`${environment.apiUrl}/users/${id}/role/`, { role });
  }

  activate(id: number): Observable<AuthUser> {
    return this.http.patch<AuthUser>(`${environment.apiUrl}/users/${id}/activate/`, {});
  }

  deactivate(id: number): Observable<AuthUser> {
    return this.http.patch<AuthUser>(`${environment.apiUrl}/users/${id}/deactivate/`, {});
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/users/${id}/`);
  }
}
