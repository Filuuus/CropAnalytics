import { Routes } from "@angular/router";

import HomeRoutes from "./home/Home.routes";
import DashboardRoutes from "./dashboard/Dashboard.routes";
import AnalyticsRoutes from "./analytics/Analytics.routes";
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
];
