import { Component, input, ChangeDetectionStrategy } from "@angular/core";
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
  constructor(private router: Router) {}

  /** Style props */
  headerFlexDirection = input<string | number | undefined>("");
  navFlex = input<string | number | undefined>("");
  navJustifyContent = input<string | number | undefined>("");
  navGap = input<string | number | undefined>("");
  navMargin = input<string | number | undefined>("");
  navAlignSelf = input<string | number | undefined>("");
  containerMargin = input<string | number | undefined>("");
  homeColor = input<string | number | undefined>("");
  dashboardColor = input<string | number | undefined>("");
  analyticsColor = input<string | number | undefined>("");
  /** Action props */
  onHomeTextClick = input<() => void>(() => {});
  onAnalyticsTextClick = input<() => void>(() => {});
  onDashboardTextClick = input<() => void>(() => {});

  onDashboardTextClick1() {
    this.router.navigate(["/1920w-light2"]);
  }

  onUploadDataTextClick() {
    // Please sync "1920w light" to the project
  }

  onAnalyticsTextClick1() {
    this.router.navigate(["/1920w-light1"]);
  }
}
