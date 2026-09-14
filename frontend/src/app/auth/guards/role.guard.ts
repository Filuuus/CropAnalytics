import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService, UserRole } from '../services/auth.service';

export const roleGuard: CanActivateFn = (route) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const roles = (route.data['roles'] ?? []) as UserRole[];

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/auth/login']);
  }

  if (roles.length === 0 || authService.hasAnyRole(roles)) {
    return true;
  }

  return router.createUrlTree([authService.dashboardFor()]);
};
