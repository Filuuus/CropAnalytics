import { Component, ChangeDetectionStrategy, HostListener, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router } from "@angular/router";

import { ThemePreference, ThemeService } from "../../services/theme.service";

@Component({
  selector: "header-1",

  imports: [CommonModule],
  templateUrl: "./Header.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Header {
  readonly isThemeMenuOpen = signal(false);

  constructor(
    private router: Router,
    public themeService: ThemeService,
  ) {}

  onHomeClick() {
    this.router.navigate(["/"]);
  }

  onDashboardClick() {
    this.router.navigate(["/dashboard"]);
  }

  onAnalyticsClick() {
    this.router.navigate(["/analytics"]);
  }

  onLoginClick() {
    this.router.navigate(["/auth/login"]);
  }

  setTheme(preference: ThemePreference): void {
    this.themeService.setPreference(preference);
    this.isThemeMenuOpen.set(false);
  }

  toggleThemeMenu(): void {
    this.isThemeMenuOpen.update((current) => !current);
  }

  @HostListener("document:click")
  onDocumentClick(): void {
    this.isThemeMenuOpen.set(false);
  }
}
