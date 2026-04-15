import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { CommonModule } from "@angular/common";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { map } from "rxjs";

import { Header } from "../../../shared/components/header/Header";
import { Footer } from "../../../shared/components/footer/Footer";

type AuthMode = "login" | "register";

@Component({
  selector: "auth",
  imports: [CommonModule, ReactiveFormsModule, RouterLink, Header, Footer],
  templateUrl: "./Auth.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Auth {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly mode = toSignal(
    this.route.data.pipe(
      map((data) => ((data["mode"] as AuthMode) ?? "login")),
    ),
    { initialValue: "login" as AuthMode },
  );

  readonly submitted = signal(false);
  readonly emailVerificationNotice = signal(false);
  readonly loginNotice = signal(false);

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
    this.emailVerificationNotice.set(false);
    this.loginNotice.set(false);
    this.authForm.reset();
    this.router.navigate([`/auth/${mode}`]);
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.emailVerificationNotice.set(false);
    this.loginNotice.set(false);

    if (this.isRegisterMode()) {
      this.authForm.controls.name.addValidators([Validators.required, Validators.minLength(2)]);
    } else {
      this.authForm.controls.name.clearValidators();
    }

    this.authForm.controls.name.updateValueAndValidity({ emitEvent: false });

    if (this.authForm.invalid) {
      return;
    }

    if (this.isRegisterMode()) {
      this.emailVerificationNotice.set(true);
      return;
    }

    this.loginNotice.set(true);
  }

  isControlInvalid(controlName: "name" | "email" | "password"): boolean {
    const control = this.authForm.controls[controlName];
    return control.invalid && (control.touched || this.submitted());
  }
}
