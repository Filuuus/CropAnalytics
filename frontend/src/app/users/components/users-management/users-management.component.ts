import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Header } from '../../../shared/components/header/Header';
import { Footer } from '../../../shared/components/footer/Footer';
import { AuthUser } from '../../../auth/services/auth.service';
import { AdminUsersService, UserFilters } from '../../services/admin-users.service';

type PendingUserAction =
  | { kind: 'role'; user: AuthUser; role: 'JEFE' | 'INVESTIGADOR' }
  | { kind: 'status'; user: AuthUser }
  | { kind: 'delete'; user: AuthUser };

@Component({
  selector: 'users-management',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, Header, Footer],
  templateUrl: './users-management.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.display]': "'contents'" },
})
export class UsersManagementComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly usersService = inject(AdminUsersService);

  readonly users = signal<AuthUser[]>([]);
  readonly loading = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  readonly confirmDialogState = signal<'idle' | 'confirming' | 'canceling'>('idle');
  readonly pendingAction = signal<PendingUserAction | null>(null);

  readonly confirmDialog = computed(() => {
    const action = this.pendingAction();
    if (!action) {
      return null;
    }

    const name = action.user.name || action.user.email;
    if (action.kind === 'role') {
      return {
        title: 'Cambiar rol',
        description: `Se cambiara el rol de ${name} a ${action.role}.`,
        confirmLabel: 'Si, cambiar rol',
        tone: 'blue',
      };
    }

    if (action.kind === 'status') {
      const willDeactivate = action.user.is_active;
      return {
        title: willDeactivate ? 'Inhabilitar usuario' : 'Activar usuario',
        description: willDeactivate
          ? `${name} no podra iniciar sesion mientras este inhabilitado.`
          : `${name} recuperara el acceso a la plataforma.`,
        confirmLabel: willDeactivate ? 'Si, inhabilitar' : 'Si, activar',
        tone: willDeactivate ? 'amber' : 'green',
      };
    }

    return {
      title: 'Eliminar usuario',
      description: `Se eliminara permanentemente la cuenta de ${name}. Esta accion no se puede deshacer.`,
      confirmLabel: 'Si, eliminar',
      tone: 'red',
    };
  });

  readonly filtersForm = this.fb.nonNullable.group({
    search: [''],
    role: [''],
    is_active: [''],
  });

  readonly totalActive = computed(() => this.users().filter((user) => user.is_active).length);
  readonly totalJefes = computed(() => this.users().filter((user) => user.role === 'JEFE').length);

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading.set(true);
    this.error.set('');
    this.usersService.list(this.filtersForm.getRawValue() as UserFilters).subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error.error?.detail ?? 'No se pudieron cargar los usuarios.');
        this.loading.set(false);
      },
    });
  }

  clearFilters(): void {
    this.filtersForm.reset();
    this.loadUsers();
  }

  changeRole(user: AuthUser, role: string, event?: Event): void {
    if (event?.target instanceof HTMLSelectElement) {
      event.target.value = user.role;
    }
    if (role !== 'JEFE' && role !== 'INVESTIGADOR') {
      return;
    }
    if (role === user.role) {
      return;
    }
    this.openConfirmation({ kind: 'role', user, role });
  }

  toggleStatus(user: AuthUser): void {
    this.openConfirmation({ kind: 'status', user });
  }

  deleteUser(user: AuthUser): void {
    this.openConfirmation({ kind: 'delete', user });
  }

  cancelConfirmation(): void {
    if (this.confirmDialogState() !== 'idle') {
      return;
    }
    this.confirmDialogState.set('canceling');
    window.setTimeout(() => {
      this.pendingAction.set(null);
      this.confirmDialogState.set('idle');
    }, 180);
  }

  confirmAction(): void {
    const action = this.pendingAction();
    if (!action || this.confirmDialogState() !== 'idle') {
      return;
    }

    this.confirmDialogState.set('confirming');
    window.setTimeout(() => this.executePendingAction(action), 220);
  }

  private openConfirmation(action: PendingUserAction): void {
    this.error.set('');
    this.message.set('');
    this.confirmDialogState.set('idle');
    this.pendingAction.set(action);
  }

  private closeConfirmation(): void {
    this.pendingAction.set(null);
    this.confirmDialogState.set('idle');
  }

  private executePendingAction(action: PendingUserAction): void {
    if (action.kind === 'role') {
      this.runAction(this.usersService.setRole(action.user.id, action.role), 'Rol actualizado.');
      return;
    }

    if (action.kind === 'status') {
      const request = action.user.is_active
        ? this.usersService.deactivate(action.user.id)
        : this.usersService.activate(action.user.id);
      this.runAction(request, action.user.is_active ? 'Usuario inhabilitado.' : 'Usuario activado.');
      return;
    }

    this.usersService.delete(action.user.id).subscribe({
      next: () => {
        this.message.set('Usuario eliminado.');
        this.closeConfirmation();
        this.loadUsers();
      },
      error: (error) => {
        this.error.set(error.error?.detail ?? 'No se pudo eliminar el usuario.');
        this.closeConfirmation();
      },
    });
  }

  private runAction(request: ReturnType<AdminUsersService['activate']>, successMessage: string): void {
    this.error.set('');
    this.message.set('');
    request.subscribe({
      next: () => {
        this.message.set(successMessage);
        this.closeConfirmation();
        this.loadUsers();
      },
      error: (error) => {
        this.error.set(error.error?.detail ?? 'Operacion no permitida.');
        this.closeConfirmation();
      },
    });
  }
}
