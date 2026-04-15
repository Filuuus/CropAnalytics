import { Routes } from "@angular/router";

import { Auth } from "./components/auth/Auth";

const routes: Routes = [
  {
    path: "login",
    component: Auth,
    data: { mode: "login" },
  },
  {
    path: "register",
    component: Auth,
    data: { mode: "register" },
  },
];

export default routes;
