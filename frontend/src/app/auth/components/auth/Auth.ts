import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  NgZone,
  computed,
  inject,
  signal,
} from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { CommonModule } from "@angular/common";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { map } from "rxjs";

import { Header } from "../../../shared/components/header/Header";
import { Footer } from "../../../shared/components/footer/Footer";
import { environment } from "../../../../environments/environment";
import { AuthService } from "../../services/auth.service";

type AuthMode = "login" | "register";

declare const google: any;

@Component({
  selector: "auth",
  imports: [CommonModule, ReactiveFormsModule, RouterLink, Header, Footer],
  templateUrl: "./Auth.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Auth implements AfterViewInit {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);
  private readonly zone = inject(NgZone);

  readonly mode = toSignal(
    this.route.data.pipe(
      map((data) => ((data["mode"] as AuthMode) ?? "login")),
    ),
    { initialValue: "login" as AuthMode },
  );

  readonly submitted = signal(false);
  readonly successNotice = signal("");
  readonly errorNotice = signal("");
  readonly loading = signal(false);
  readonly googleReady = signal(false);

  readonly authForm = this.fb.nonNullable.group({
    name: ["", [Validators.required, Validators.minLength(2)]],
    email: ["", [Validators.required, Validators.email]],
    password: ["", [Validators.required, Validators.minLength(8)]],
  });

  readonly isRegisterMode = computed(() => this.mode() === "register");

  onSwitchMode(mode: AuthMode): void {
    if (mode === this.mode()) {
      return;
    }

    this.submitted.set(false);
    this.successNotice.set("");
    this.errorNotice.set("");
    this.authForm.reset();
    this.router.navigate([`/auth/${mode}`]);
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.successNotice.set("");
    this.errorNotice.set("");

    if (this.isRegisterMode()) {
      this.authForm.controls.name.addValidators([Validators.required, Validators.minLength(2)]);
    } else {
      this.authForm.controls.name.clearValidators();
    }

    this.authForm.controls.name.updateValueAndValidity({ emitEvent: false });

    if (this.authForm.invalid) {
      return;
    }

    this.loading.set(true);
    const { name, email, password } = this.authForm.getRawValue();
    const request = this.isRegisterMode()
      ? this.authService.register({ name, email, password })
      : this.authService.login({ email, password });

    request.subscribe({
      next: () => {
        this.loading.set(false);
        this.authService.redirectByRole();
      },
      error: (error) => {
        this.loading.set(false);
        this.errorNotice.set(this.extractError(error));
      },
    });
  }


  ngAfterViewInit(): void {
    if (!environment.googleClientId) {
      return;
    }

    this.loadGoogleScript()
      .then(() => {
        google.accounts.id.initialize({
          client_id: environment.googleClientId,
          callback: (response: { credential: string }) => {
            this.zone.run(() => this.handleGoogleCredential(response.credential));
          },
        });

        // Renderizar el boton oficial de Google
        google.accounts.id.renderButton(
          document.getElementById("googleBtn"),
          {
            theme: "outline",
            size: "large",
            width: 380, // Ajustar al ancho del contenedor
            text: "continue_with",
            shape: "rectangular",
          }
        );

        this.googleReady.set(true);
      })
      .catch(() => {
        this.errorNotice.set("No se pudo cargar Google Identity Services.");
      });
  }

  private handleGoogleCredential(credential: string): void {
    this.loading.set(true);
    this.authService.googleLogin(credential).subscribe({
      next: () => {
        this.loading.set(false);
        this.authService.redirectByRole();
      },
      error: (error) => {
        this.loading.set(false);
        this.errorNotice.set(this.extractError(error));
      },
    });
  }

  private loadGoogleScript(): Promise<void> {
    if (typeof google !== "undefined") {
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const existingScript = document.querySelector<HTMLScriptElement>(
        'script[src="https://accounts.google.com/gsi/client"]',
      );
      if (existingScript) {
        existingScript.addEventListener("load", () => resolve());
        existingScript.addEventListener("error", () => reject());
        return;
      }

      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject();
      document.head.appendChild(script);
    });
  }

  private extractError(error: any): string {
    const detail = error?.error?.detail ?? error?.error?.non_field_errors?.[0];
    if (detail) {
      return detail;
    }
    const firstField = error?.error && Object.values(error.error)[0];
    if (Array.isArray(firstField) && firstField.length) {
      return String(firstField[0]);
    }
    if (this.isRegisterMode()) {
      return "No se pudo crear la cuenta. Revisa los datos.";
    }
    return "No se pudo iniciar sesion.";
  }

  isControlInvalid(controlName: "name" | "email" | "password"): boolean {
    const control = this.authForm.controls[controlName];
    return control.invalid && (control.touched || this.submitted());
  }
}
