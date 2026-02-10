import { Component, ChangeDetectionStrategy } from "@angular/core";
import { Router } from "@angular/router";
import { Header } from "../../../shared/components/header/Header";
import { Main } from "../main/Main";
import { Footer } from "../../../shared/components/footer/Footer";

@Component({
  selector: "analytics",

  imports: [Header, Main, Footer],
  templateUrl: "./Analytics.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Analytics {
  constructor(private router: Router) { }


}
