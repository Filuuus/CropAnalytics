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
  readonly isLogoutDialogOpen = signal(false);
  readonly logoutDialogState = signal<"idle" | "confirming" | "canceling">("idle");

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

  onAboutClick() {
    this.router.navigate(["/about"]);
  }

  onLogoutClick() {
    this.isThemeMenuOpen.set(false);
    this.isUploadMenuOpen.set(false);
    this.logoutDialogState.set("idle");
    this.isLogoutDialogOpen.set(true);
  }

  onCancelLogout() {
    if (this.logoutDialogState() !== "idle") {
      return;
    }
    this.logoutDialogState.set("canceling");
    window.setTimeout(() => {
      this.isLogoutDialogOpen.set(false);
      this.logoutDialogState.set("idle");
    }, 180);
  }

  onConfirmLogout() {
    if (this.logoutDialogState() !== "idle") {
      return;
    }
    this.logoutDialogState.set("confirming");
    window.setTimeout(() => {
      this.isLogoutDialogOpen.set(false);
      this.logoutDialogState.set("idle");
      this.authService.logout();
    }, 260);
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
