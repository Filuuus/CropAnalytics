import { Routes } from "@angular/router";

import HomeRoutes from "./home/Home.routes";
import DashboardRoutes from "./dashboard/Dashboard.routes";
import AnalyticsRoutes from "./analytics/Analytics.routes";
import AuthRoutes from "./auth/Auth.routes";
import { authGuard } from "./auth/guards/auth.guard";
import { roleGuard } from "./auth/guards/role.guard";
export const routes: Routes = [
  {
    path: "",
    children: HomeRoutes,
  },
  {
    path: "dashboard",
    loadComponent: () => import("./calculator/calculator.component").then(m => m.CalculatorComponent),
  },
  {
    path: "dashboard-jefe",
    loadComponent: () => import("./calculator/calculator.component").then(m => m.CalculatorComponent),
  },
  {
    path: "dashboard-investigador",
    children: AnalyticsRoutes,
  },
  {
    path: "analytics",
    children: AnalyticsRoutes,
  },
  {
    path: "auth",
    children: AuthRoutes,
  },
  {
    path: "captura",
    canActivate: [authGuard],
    children: [
      {
        path: "jefe",
        loadComponent: () => import('./upload/jefe/jefe.component').then(m => m.JefeComponent),
        canActivate: [roleGuard],
        data: { roles: ["JEFE", "SADMIN"] },
      },
      {
        path: "investigador",
        loadComponent: () => import('./upload/investigador/investigador.component').then(m => m.InvestigadorComponent),
        canActivate: [roleGuard],
        data: { roles: ["INVESTIGADOR", "JEFE", "SADMIN"] },
      }
    ]
  },
  {
    path: "upload-data",
    redirectTo: "captura/investigador",
    pathMatch: "full",
  },
  {
    path: "users-management",
    loadComponent: () => import("./users/components/users-management/users-management.component").then(m => m.UsersManagementComponent),
    canActivate: [roleGuard],
    data: { roles: ["JEFE", "SADMIN"] },
  },
  {
    path: "calculator",
    loadComponent: () => import("./calculator/calculator.component").then(m => m.CalculatorComponent),
  },
  {
    path: "about",
    loadComponent: () => import("./about/components/about/About").then(m => m.About),
  },
];
