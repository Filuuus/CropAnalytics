import { Component, ChangeDetectionStrategy } from "@angular/core";
import { Router } from "@angular/router";
import { Header } from "../../../shared/components/header/Header";
import { Footer } from "../../../shared/components/footer/Footer";

@Component({
  selector: "dashboard",

  imports: [Header, Footer],
  templateUrl: "./Dashboard.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Dashboard {
  constructor(private router: Router) { }


}
