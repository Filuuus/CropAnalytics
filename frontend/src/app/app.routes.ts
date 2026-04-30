import { Routes } from "@angular/router";

import HomeRoutes from "./home/Home.routes";
import DashboardRoutes from "./dashboard/Dashboard.routes";
import AnalyticsRoutes from "./analytics/Analytics.routes";
import AuthRoutes from "./auth/Auth.routes";
export const routes: Routes = [
  {
    path: "",
    children: HomeRoutes,
  },
  {
    path: "dashboard",
    children: DashboardRoutes,
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
    children: [
      {
        path: "jefe",
        loadComponent: () => import('./upload/jefe/jefe.component').then(m => m.JefeComponent)
      },
      {
        path: "investigador",
        loadComponent: () => import('./upload/investigador/investigador.component').then(m => m.InvestigadorComponent)
      }
    ]
  },
];
