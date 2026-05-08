import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from '../services/auth.service';

export const jwtInterceptor: HttpInterceptorFn = (request, next) => {
  const authService = inject(AuthService);
  const token = authService.getAccessToken();
  const isAuthRefresh = request.url.includes('/auth/token/refresh/');

  const authRequest =
    token && !isAuthRefresh
      ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : request;

  return next(authRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || isAuthRefresh || !authService.getRefreshToken()) {
        return throwError(() => error);
      }

      return authService.refreshAccessToken().pipe(
        switchMap(({ access }) =>
          next(request.clone({ setHeaders: { Authorization: `Bearer ${access}` } })),
        ),
        catchError((refreshError) => {
          authService.logout();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
