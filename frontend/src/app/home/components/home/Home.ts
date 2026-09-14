import { Component, ChangeDetectionStrategy } from "@angular/core";
import { Router } from "@angular/router";
import { Header } from "../../../shared/components/header/Header";
import { Footer } from "../../../shared/components/footer/Footer";
import { CommonModule } from "@angular/common";

@Component({
  selector: "home",
  imports: [CommonModule, Header, Footer],
  templateUrl: "./Home.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Home {
  constructor(private router: Router) { }

  onGoToDashboardClick() {
    this.router.navigate(["/dashboard"]);
  }

  onAboutClick() {
    this.router.navigate(["/about"]);
  }
}
