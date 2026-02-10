import { Component, ChangeDetectionStrategy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router } from "@angular/router";

@Component({
  selector: "header-1",

  imports: [CommonModule],
  templateUrl: "./Header.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Header {
  constructor(private router: Router) { }

  onHomeClick() {
    this.router.navigate(["/"]);
  }

  onDashboardClick() {
    this.router.navigate(["/dashboard"]);
  }

  onAnalyticsClick() {
    this.router.navigate(["/analytics"]);
  }
}
