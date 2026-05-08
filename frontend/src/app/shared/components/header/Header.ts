import { Component, ChangeDetectionStrategy, HostListener, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router } from "@angular/router";

import { ThemePreference, ThemeService } from "../../services/theme.service";
import { AuthService } from "../../../auth/services/auth.service";

@Component({
  selector: "header-1",

  imports: [CommonModule],
  templateUrl: "./Header.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Header {
  readonly isThemeMenuOpen = signal(false);
  readonly isUploadMenuOpen = signal(false);

  constructor(
    private router: Router,
    public themeService: ThemeService,
    public authService: AuthService,
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

  onUsersClick() {
    this.router.navigate(["/users-management"]);
  }

  onLogoutClick() {
    this.authService.logout();
  }

  onJefeClick() {
    this.router.navigate(["/captura/jefe"]);
    this.isUploadMenuOpen.set(false);
  }

  onInvestigadorClick() {
    this.router.navigate(["/captura/investigador"]);
    this.isUploadMenuOpen.set(false);
  }

  onUploadDataClick() {
    this.onInvestigadorClick();
  }

  setTheme(preference: ThemePreference): void {
    this.themeService.setPreference(preference);
    this.isThemeMenuOpen.set(false);
  }

  toggleThemeMenu(): void {
    this.isThemeMenuOpen.update((current) => !current);
    this.isUploadMenuOpen.set(false);
  }

  toggleUploadMenu(): void {
    this.isUploadMenuOpen.update((current) => !current);
    this.isThemeMenuOpen.set(false);
  }

  @HostListener("document:click")
  onDocumentClick(): void {
    this.isThemeMenuOpen.set(false);
    this.isUploadMenuOpen.set(false);
  }
}
