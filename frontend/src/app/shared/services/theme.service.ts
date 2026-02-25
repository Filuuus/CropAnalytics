import { DestroyRef, Injectable, inject, signal } from "@angular/core";

export type ThemePreference = "light" | "dark" | "system";

@Injectable({ providedIn: "root" })
export class ThemeService {
  private static readonly storageKey = "theme";

  private readonly destroyRef = inject(DestroyRef);
  private mediaQuery: MediaQueryList | null = null;

  readonly preference = signal<ThemePreference>("system");
  readonly resolvedTheme = signal<"light" | "dark">("light");

  constructor() {
    if (typeof window === "undefined") {
      return;
    }

    this.mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    this.preference.set(this.readPreference());
    this.applyTheme();
    this.watchSystemTheme();
  }

  setPreference(preference: ThemePreference): void {
    this.preference.set(preference);
    try {
      window.localStorage.setItem(ThemeService.storageKey, preference);
    } catch {
      // Keep manual theme switching working even if storage is blocked.
    }
    this.applyTheme();
  }

  cyclePreference(): void {
    const nextMap: Record<ThemePreference, ThemePreference> = {
      light: "dark",
      dark: "system",
      system: "light",
    };

    this.setPreference(nextMap[this.preference()]);
  }

  isActive(preference: ThemePreference): boolean {
    return this.preference() === preference;
  }

  getPreferenceLabel(): string {
    const labels: Record<ThemePreference, string> = {
      light: "Claro",
      dark: "Oscuro",
      system: "Sistema",
    };

    return labels[this.preference()];
  }

  private readPreference(): ThemePreference {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(ThemeService.storageKey);
    } catch {
      stored = null;
    }

    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }

    return "system";
  }

  private applyTheme(): void {
    const root = document.documentElement;
    const preference = this.preference();
    const effectiveTheme: "light" | "dark" =
      preference === "system" ? (this.mediaQuery?.matches ? "dark" : "light") : preference;

    this.resolvedTheme.set(effectiveTheme);
    root.classList.toggle("dark", effectiveTheme === "dark");
    root.style.colorScheme = effectiveTheme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", effectiveTheme === "dark" ? "#0f172a" : "#f3f8ff");
  }

  private watchSystemTheme(): void {
    if (!this.mediaQuery) {
      return;
    }

    const onChange = () => {
      if (this.preference() === "system") {
        this.applyTheme();
      }
    };

    this.mediaQuery.addEventListener("change", onChange);
    this.destroyRef.onDestroy(() => this.mediaQuery?.removeEventListener("change", onChange));
  }
}
